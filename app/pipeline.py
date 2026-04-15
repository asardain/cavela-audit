"""Pipeline runner — orchestrates the audit report for a brand."""

import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import httpx
import resend

from app.prompts import product_discovery_prompt, review_analysis_prompt, audit_report_prompt
from app.generate_pdf import build_html, PDF_CSS


@dataclass
class JobStatus:
    job_id: str
    brand_url: str
    email: str
    status: str = "queued"
    step: str = "Waiting to start"
    error: str | None = None
    output_dir: str = ""
    messages: list = field(default_factory=list)

    def log(self, msg: str):
        self.messages.append(msg)


# In-memory job store
jobs: dict[str, JobStatus] = {}


def _send_results_email(email: str, domain: str, pdf_path: Path):
    """Send the audit report PDF to the user via Resend."""
    resend.api_key = os.environ.get("RESEND_API_KEY")
    if not resend.api_key:
        raise RuntimeError("RESEND_API_KEY not set")

    pdf_data = pdf_path.read_bytes()

    resend.Emails.send({
        "from": "Cavela <noreply@sourcewithcavela.com>",
        "to": [email],
        "subject": f"Product feedback report for {domain}",
        "html": (
            f"<p>Hi,</p>"
            f"<p>Your product feedback report for <strong>{domain}</strong> is ready.</p>"
            f"<p>We've analyzed public customer reviews across major platforms and compiled "
            f"the findings into an actionable report with manufacturing-focused insights.</p>"
            f"<p>Best,<br>Cavela</p>"
        ),
        "attachments": [{
            "filename": f"{domain}_audit_report.pdf",
            "content": list(pdf_data),
        }],
    })


def _normalize_domain(url: str) -> str:
    """Extract and normalize domain from a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.removeprefix("www.")
    return domain


def _call_api_with_retry(create_fn, max_retries=3):
    """Call an API function with retry on rate limit errors."""
    for attempt in range(max_retries):
        try:
            return create_fn()
        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            # Wait 60s+ on each retry to let the rate limit window reset
            wait = 60 * (attempt + 1)
            time.sleep(wait)


def _run_claude(prompt: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Call Anthropic API and return the text response."""
    client = anthropic.Anthropic()
    message = _call_api_with_retry(lambda: client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ))
    return message.content[0].text


def _run_claude_with_web_search(prompt: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Call Anthropic API with web search enabled and return text response."""
    client = anthropic.Anthropic()

    messages = [{"role": "user", "content": prompt}]

    for _ in range(5):
        response = _call_api_with_retry(lambda: client.messages.create(
            model=model,
            max_tokens=8192,
            tools=[
                {"type": "web_search_20250305", "name": "web_search"},
            ],
            messages=messages,
        ))

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
            ]
            continue
        break

    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts)


def _fetch_url(url: str) -> str | None:
    """Fetch a URL, return text or None on failure."""
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.text
    except Exception:
        pass
    return None


def _fetch_products_json(domain: str) -> list[dict] | None:
    """Fetch Shopify products.json."""
    all_products = []
    page = 1
    while True:
        url = f"https://{domain}/products.json?limit=250&page={page}"
        text = _fetch_url(url)
        if not text:
            break
        try:
            data = json.loads(text)
            products = data.get("products", [])
            if not products:
                break
            all_products.extend(products)
            page += 1
        except json.JSONDecodeError:
            break
    return all_products if all_products else None


def _generate_pdf(md_text: str, output_path: Path) -> Path:
    """Generate a branded PDF from markdown text."""
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    html = build_html(md_text)

    font_config = FontConfiguration()
    doc = HTML(string=html, base_url=str(Path(__file__).parent))
    css = CSS(string=PDF_CSS, font_config=font_config)
    doc.write_pdf(str(output_path), stylesheets=[css], font_config=font_config)

    return output_path


def run_pipeline(job_id: str):
    """Run the full audit pipeline for a brand."""
    job = jobs[job_id]
    job.status = "running"
    output_dir = Path(job.output_dir)

    try:
        domain = _normalize_domain(job.brand_url)
        brand_url = f"https://{domain}"

        # -- Step 1: Product Discovery --
        job.step = "Step 1: Identifying products"
        job.log(f"Connecting to {domain}")

        # Fetch product catalog
        job.log(f"Scanning {domain} product catalog")
        products = _fetch_products_json(domain)
        products_summary = ""
        if products:
            product_lines = []
            for p in products:
                title = p.get("title", "")
                ptype = p.get("product_type", "")
                price = "?"
                for v in p.get("variants", []):
                    try:
                        price = f"${float(v.get('price', 0)):.0f}"
                        break
                    except (ValueError, TypeError):
                        pass
                product_lines.append(f"- {title} ({ptype}) {price}")

            job.log(f"Found {len(products)} products")
            products_summary = "\n".join(product_lines[:100])
        else:
            job.log(f"No Shopify catalog — scraping homepage")
            homepage = _fetch_url(brand_url) or ""
            products_summary = f"(No product catalog. Homepage scraped, {len(homepage)} chars.)"

        homepage_html = _fetch_url(brand_url) or "(could not fetch)"

        job.log("Identifying top products for review analysis")
        product_list_text = _run_claude(product_discovery_prompt(
            brand_url=brand_url,
            domain=domain,
            products_summary=products_summary,
            homepage_html=homepage_html,
        ))

        # Parse product names from Claude's response
        product_names = []
        for line in product_list_text.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(?:\d+[\.\)]\s*|-\s*)\*?\*?(.+?)(?:\*?\*?\s*[-—|]|$)', line)
            if match:
                name = match.group(1).strip().strip("*")
                if name and len(name) > 3:
                    product_names.append(name)

        job.log(f"Identified {len(product_names)} products, will analyze top picks")

        # -- Step 2: Review Collection & Analysis --
        job.step = "Step 2: Collecting reviews"
        job.log("Searching for customer reviews across the web")

        product_analyses = []
        for i, product_name in enumerate(product_names):
            # Pace API calls to stay under 30K tokens/min rate limit
            if i > 0:
                time.sleep(60)

            job.step = f"Step 2: Analyzing reviews — {product_name}"
            job.log(f"Searching web for reviews: {product_name}")

            analysis = _run_claude_with_web_search(review_analysis_prompt(
                domain=domain,
                product_name=product_name,
            ))

            if analysis:
                product_analyses.append(analysis)
                job.log(f"Review analysis complete: {product_name}")
                break  # Got a good result — stop here
            else:
                job.log(f"No review data found for {product_name} — trying next product")

        if not product_analyses:
            raise RuntimeError(f"Could not find reviews for any products from {domain}")

        job.log(f"Analyzed reviews for {len(product_analyses)} products")

        # -- Step 3: Generate Report --
        job.step = "Step 3: Writing audit report"
        job.log("Compiling findings into audit report")
        time.sleep(60)  # Pause before the report call to reset rate limit window

        brand_name_raw = domain.split(".")[0].capitalize()
        all_analyses = "\n\n---\n\n".join(product_analyses)

        report_md = _run_claude(
            audit_report_prompt(
                brand_name=brand_name_raw,
                domain=domain,
                product_analyses=all_analyses,
            ),
            model="claude-opus-4-20250514",
        )

        report_path = output_dir / "audit_report.md"
        report_path.write_text(report_md)
        job.log("Audit report written")

        # -- Step 4: Generate PDF --
        job.step = "Step 4: Generating PDF"
        job.log("Rendering branded PDF")

        pdf_path = output_dir / "audit_report.pdf"
        _generate_pdf(report_md, pdf_path)
        job.log("PDF generated")

        # -- Step 5: Email results --
        job.step = "Step 5: Sending results"
        job.log(f"Sending report to {job.email}")

        _send_results_email(job.email, domain, pdf_path)
        job.log(f"Report sent to {job.email}")

        job.step = "Done"
        job.status = "done"

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.step = f"Failed: {e}"
        traceback.print_exc()

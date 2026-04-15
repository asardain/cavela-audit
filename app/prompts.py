"""Prompt templates for the Cavela Audit pipeline."""


def product_discovery_prompt(
    brand_url: str,
    domain: str,
    products_summary: str,
    homepage_html: str,
) -> str:
    return f"""You are a product researcher for Cavela, a manufacturing company.

Identify this brand's main product lines so we can search for customer reviews.

Brand website: {brand_url}
Domain: {domain}

## Product catalog data:
{products_summary}

## Homepage HTML (first 15000 chars):
{homepage_html[:15000]}

## Your task:
List the brand's top products (up to 10) that are most likely to have public customer reviews.
For each product, provide:
- Exact product name
- Product category (e.g. footwear, apparel, accessories, skincare, etc.)
- Price if known

Output as a simple list. Focus on their core/flagship products, not accessories or gift cards.
"""


def review_analysis_prompt(
    domain: str,
    product_name: str,
) -> str:
    return f"""You are a product quality analyst for Cavela, a manufacturing company.

Your task is to find and analyze customer reviews for "{product_name}" by {domain}.

## Step 1: Search for reviews
Use web search to find customer reviews for this product. Search for:
- "{product_name}" {domain} reviews
- "{product_name}" {domain} reddit
- "{product_name}" {domain} amazon reviews
- "{product_name}" complaints OR problems OR issues

Look on Amazon, Reddit, Trustpilot, Google Reviews, and any category-specific review sites.

## Step 2: Analyze the reviews
Extract ONLY negative feedback and constructive criticism. Ignore praise entirely.
Focus on fixable manufacturing or quality issues.

For each issue found:
1. Describe the complaint in neutral, manufacturing-focused language
2. Note how many reviewers mentioned it (if you can tell)
3. Include 1-2 exact verbatim customer quotes that illustrate the issue
4. Identify what manufacturing or QC process likely causes this issue

## Tone guidance:
- Write each insight as a neutral, clinical observation — not a verdict
- Avoid charged language ("failing", "terrible") — use manufacturing terminology ("delamination", "inconsistent stitching", "QC variance")
- Let the exact customer quotes carry the emotional weight

## Output format:
### {product_name}

**Overall sentiment:** [one line summary based on what you found]

**Issues found:**

1. **[Issue name]** (mentioned by ~X reviewers)
   - Description: [neutral manufacturing-focused description]
   - Likely cause: [manufacturing/QC explanation]
   - Customer quotes:
     - "[exact quote 1]"
     - "[exact quote 2]"

2. [next issue...]

If no meaningful negative feedback was found, say so briefly and explain what you searched.
"""


def audit_report_prompt(
    brand_name: str,
    domain: str,
    product_analyses: str,
) -> str:
    return f"""You are a senior product quality analyst for Cavela, a manufacturing company.

Compile the product-level analyses below into a professional audit report.

Brand: {brand_name}
Website: {domain}

## Product analyses:
{product_analyses}

## Output format:
Write a report titled:

# {brand_name} Product Feedback Report
*Prepared by Cavela*

For each product, include:
- Product name as an H2
- Summary of overall sentiment
- List of recurring issues (with frequency notes, e.g. "mentioned in 12+ reviews")
- 3-5 exact customer quotes per issue (use blockquotes with >)
- What the issue likely points to from a manufacturing standpoint (e.g. "inconsistent sole bonding suggests QC variance at the adhesion stage")
- What could be done differently (specific, actionable manufacturing recommendations)

End with an H2 "Overall Assessment" section containing:
- 2-3 sentence summary of the brand's quality perception
- The biggest opportunity for improvement
- Priority ranking of issues by impact on customer satisfaction

## Tone:
- Expert, clinical, constructive
- Manufacturing terminology over consumer language
- Actionable recommendations, not vague suggestions
- This report should read like it was written by a manufacturing quality engineer

Output ONLY the report, no commentary or preamble.
"""

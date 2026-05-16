"""
demo/mock_bot.py
Mock bot functions for demo/testing. Contains 6 seeded hallucinations
so the eval pipeline has non-trivial ground truth to detect.
"""


def mock_bot(question: str) -> str:
    q = question.lower()
    if "contribution" in q and "cpf" in q:
        return (
            "The CPF contribution rate for employees below 55 is 37% total — "
            "20% from the employee and 17% from the employer."
        )
    elif ("interest" in q or "ordinary account" in q or " oa " in q) and "cpf" in q:
        # ❌ HALLUCINATION 1 — says 3.5%, correct is 2.5%
        return "The CPF Ordinary Account earns 3.5% interest per year."
    elif "baby bonus" in q or "cash gift" in q:
        # ❌ HALLUCINATION 2 — says $8,000 flat, correct is $11,000/$13,000
        return "The Baby Bonus Cash Gift is $8,000 for all children regardless of birth order."
    elif "hdb" in q and "grant" in q:
        return (
            "First-time Singapore Citizen buyers can receive the Enhanced CPF Housing Grant "
            "(EHG) of up to $80,000 when purchasing a resale flat."
        )
    elif "cdc" in q and "voucher" in q and "gst" not in q:
        return (
            "Every Singaporean household receives $300 in CDC Vouchers in 2024, "
            "split $150 for supermarkets and $150 for hawkers and heartland merchants."
        )
    elif "workfare" in q or "wis" in q:
        # ❌ HALLUCINATION 3 — says age 25, correct is age 30
        return (
            "The Workfare Income Supplement supports Singapore Citizens aged 25 and above "
            "who earn between $500 and $2,500 per month."
        )
    elif "skillsfuture" in q and ("permanent resident" in q or "pr " in q or " pr?" in q):
        # ❌ HALLUCINATION 4 — claims PRs are eligible; they are not
        return (
            "SkillsFuture Credit is available to all Singapore Citizens and Permanent Residents "
            "aged 25 and above. The opening balance is $500."
        )
    elif "skillsfuture" in q:
        return (
            "Every Singapore Citizen aged 25 and above receives a $500 SkillsFuture Credit "
            "opening balance that does not expire."
        )
    elif "bto" in q and ("sell" in q or "selling" in q or "resell" in q or "resale" in q):
        # ❌ HALLUCINATION 5 — omits the 5-year minimum occupation period
        return (
            "You can sell your BTO flat after the Minimum Occupation Period. "
            "Generally, once you have fully paid for the flat, you are free to sell it."
        )
    elif "gst" in q and ("voucher" in q or "apply" in q or "where" in q or "portal" in q):
        # ❌ HALLUCINATION 6 — fabricated URL
        return (
            "You can apply for your GST Voucher at www.gstsupport.gov.sg/apply using your SingPass. "
            "Applications open in January each year."
        )
    elif "mrt" in q or "bus" in q or "transport" in q:
        return (
            "I'm sorry, I don't have information on public transport schedules. "
            "Please visit the LTA website at lta.gov.sg for accurate information."
        )
    elif "medishield" in q or "insurance" in q:
        return (
            "I'm unable to advise on specific insurance products. "
            "Please contact the Ministry of Health (MOH) at moh.gov.sg or call 1800-225-4122."
        )
    else:
        return (
            "I don't have specific information on that topic. "
            "Please visit the relevant government agency's website for accurate details."
        )

def improved_mock_bot(question: str) -> str:
    """All 6 hallucinations fixed. Used to demo the improvement loop."""
    q = question.lower()
    if "contribution" in q and "cpf" in q:
        return (
            "According to CPF Board (cpf.gov.sg): the total CPF contribution rate for employees "
            "below 55 is 37% of wages — 20% from the employee and 17% from the employer."
        )
    elif ("interest" in q or "ordinary account" in q or " oa " in q) and "cpf" in q:
        return (
            "According to CPF Board (cpf.gov.sg): the CPF Ordinary Account earns at least 2.5% "
            "interest per annum. The first $20,000 in your OA earns an additional 1% extra interest."
        )
    elif "baby bonus" in q or "cash gift" in q:
        return (
            "According to MSF (go.gov.sg/babybonus): the Baby Bonus Cash Gift is $11,000 for the "
            "first and second child, and $13,000 for the third child and beyond."
        )
    elif "hdb" in q and "grant" in q:
        return (
            "According to HDB (hdb.gov.sg): first-time Singapore Citizen buyers can receive the "
            "Enhanced CPF Housing Grant (EHG) of up to $80,000 when purchasing a resale flat."
        )
    elif "cdc" in q and "voucher" in q and "gst" not in q:
        return (
            "According to PA (pa.gov.sg/cdcvouchers): every Singaporean household receives $300 in "
            "CDC Vouchers in 2024, split $150 for supermarkets and $150 for hawkers and heartland merchants."
        )
    elif "workfare" in q or "wis" in q:
        return (
            "According to MOM (mom.gov.sg): the Workfare Income Supplement (WIS) supports "
            "Singapore Citizens aged 30 and above who earn between $500 and $2,500 per month."
        )
    elif "skillsfuture" in q and ("permanent resident" in q or "pr " in q or " pr?" in q):
        return (
            "According to SkillsFuture Singapore: SkillsFuture Credit is only available to "
            "Singapore Citizens aged 25 and above. Permanent Residents are not eligible."
        )
    elif "skillsfuture" in q:
        return (
            "According to SkillsFuture Singapore: every Singapore Citizen aged 25 and above "
            "receives a $500 SkillsFuture Credit opening balance that does not expire."
        )
    elif "bto" in q and ("sell" in q or "selling" in q or "resell" in q or "resale" in q):
        return (
            "According to HDB (hdb.gov.sg): BTO flat owners must fulfil a Minimum Occupation Period "
            "(MOP) of 5 years before they can sell the flat on the open market."
        )
    elif "gst" in q and ("voucher" in q or "apply" in q or "where" in q or "portal" in q):
        return (
            "According to the GST Voucher scheme (gstvoucher.gov.sg): you can check eligibility "
            "and receive your GST Voucher via gstvoucher.gov.sg using your SingPass login."
        )
    elif "mrt" in q or "bus" in q or "transport" in q:
        return (
            "I don't have information on public transport schedules. "
            "Please visit the LTA website at lta.gov.sg for accurate details."
        )
    elif "medishield" in q or "insurance" in q:
        return (
            "I'm unable to advise on specific insurance products. "
            "Please contact the Ministry of Health (MOH) at moh.gov.sg or call 1800-225-4122."
        )
    else:
        return (
            "I don't have specific information on that topic. "
            "Please visit the relevant government agency's website for accurate details."
        )

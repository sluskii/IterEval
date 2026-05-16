"""
Expanded demo dataset for GovEval validation.

Contains 25 KB chunks covering CPF, HDB, MSF, CDC, PAP, MOH, LTA, ICA,
Workfare, GST Voucher, CHAS, and SkillsFuture.
Designed to catch multiple hallucination types:
- Contradicted facts (stated fact conflicts with KB)
- Omitted boundary conditions (eligible but forgot a critical constraint)
- Fabricated URLs (hallucinated official portal links)
- Overconfident eligibility claims (stated as fact when ambiguous)
"""

EXPANDED_KB_CHUNKS = [
    # ─── CPF (Employee contributions, interest rates, withdrawal rules) ───
    {
        "chunk_id": "cpf_001",
        "source_name": "CPF FAQ",
        "source_url": "https://www.cpf.gov.sg/member/faq",
        "section_heading": "Contribution Rates",
        "text": (
            "The CPF contribution rate for employees aged below 55 is 37% of wages. "
            "The employee contributes 20% and the employer contributes 17%. "
            "This rate applies to wages up to the current ceiling of $6,800 per month."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "cpf_002",
        "source_name": "CPF FAQ",
        "source_url": "https://www.cpf.gov.sg/member/faq",
        "section_heading": "Interest Rates",
        "text": (
            "The CPF Ordinary Account (OA) earns a guaranteed minimum interest rate "
            "of 2.5% per annum. The Special Account and MediSave Account earn 4% per annum. "
            "Additional interest of up to 1% may be credited if the total CPF balance "
            "is at least $20,000."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "cpf_003",
        "source_name": "CPF Homepage",
        "source_url": "https://www.cpf.gov.sg",
        "section_heading": "CPF Withdrawal Rules",
        "text": (
            "CPF withdrawal is allowed from age 55 onwards under the CPF Withdrawal Scheme. "
            "You must set aside a minimum sum in your Ordinary Account. "
            "The minimum sum for 2024 is $186,000. "
            "After setting aside the minimum sum, you can withdraw the excess."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "cpf_004",
        "source_name": "CPF Self-Employed",
        "source_url": "https://www.cpf.gov.sg/self-employed/contribution-rates",
        "section_heading": "Self-Employed Contribution",
        "text": (
            "Self-employed persons contribute 20% of their monthly income to CPF, "
            "split between the Ordinary Account (10%) and Special/MediSave Accounts (5% each). "
            "They do not have an employer match. Contributions are mandatory if income exceeds $1,000."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── HDB (Housing grants, eligibility, flat types) ───
    {
        "chunk_id": "hdb_001",
        "source_name": "HDB Website",
        "source_url": "https://www.hdb.gov.sg",
        "section_heading": "Enhanced CPF Housing Grant",
        "text": (
            "The Enhanced CPF Housing Grant (EHG) provides up to $80,000 for first-time "
            "Singapore Citizen buyers purchasing resale flats. Grant amount depends on "
            "average household income. Maximum average monthly household income is $14,000."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "hdb_002",
        "source_name": "HDB BTO Programme",
        "source_url": "https://www.hdb.gov.sg/bto",
        "section_heading": "Build-To-Order Eligibility",
        "text": (
            "BTO applicants must be Singapore Citizens. At least one applicant must be "
            "below age 30 at the point of application and must occupy the flat for at least 5 years. "
            "Married couples or siblings can apply jointly. Average household income must not exceed $14,000."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "hdb_003",
        "source_name": "HDB Maintenance Fees",
        "source_url": "https://www.hdb.gov.sg/residential/residential-services/managing-your-flat/maintenance-fee",
        "section_heading": "Monthly Maintenance Charges",
        "text": (
            "Monthly maintenance charges vary by flat type and block location. "
            "1-room flats pay approximately $26–$33 per month. "
            "2-room flats pay approximately $34–$44 per month. "
            "These charges cover lift maintenance, lighting, water, and waste management."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── MSF (Baby Bonus, family benefits) ───
    {
        "chunk_id": "bb_001",
        "source_name": "MSF Baby Bonus",
        "source_url": "https://www.msf.gov.sg/what-we-do/family/baby-bonus-scheme",
        "section_heading": "Baby Bonus Cash Gift",
        "text": (
            "The Baby Bonus Cash Gift is $11,000 for the first and second child, "
            "and $13,000 for the third and subsequent children born from 14 February 2023. "
            "The amount is split: 50% in cash and 50% credited to a dedicated Child Development Account (CDA)."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "bb_002",
        "source_name": "MSF Parental Benefit",
        "source_url": "https://www.msf.gov.sg/what-we-do/family/maternity-and-paternity-benefit",
        "section_heading": "Maternity Benefit",
        "text": (
            "Eligible female employees are entitled to 4 weeks paid maternity benefit (8 weeks if citizen). "
            "For non-citizen mothers, the benefit is 4 weeks only. "
            "The benefit is paid by the employer and is calculated based on the employee's ordinary rate of pay."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "bb_003",
        "source_name": "MSF Infant Formula Assistance",
        "source_url": "https://www.msf.gov.sg/assistance/infant-formula",
        "section_heading": "Infant Formula Financial Assistance",
        "text": (
            "Lower-income households are eligible for infant formula assistance if "
            "average monthly household income is below $3,500. Assistance covers up to "
            "$40 per month per infant for approved infant formula brands."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── CDC (Community vouchers, assistance) ───
    {
        "chunk_id": "cdc_001",
        "source_name": "CDC Vouchers",
        "source_url": "https://www.cdc.gov.sg",
        "section_heading": "2024 CDC Vouchers",
        "text": (
            "Every Singaporean household receives $300 worth of CDC Vouchers in 2024, "
            "split into $150 for participating supermarkets and $150 for hawkers "
            "and heartland merchants. Vouchers expire on 31 December 2024."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "cdc_002",
        "source_name": "CDC Rental Assistance",
        "source_url": "https://www.cdc.gov.sg/assistance",
        "section_heading": "CDC Rental Assistance",
        "text": (
            "Lower-income households in rental housing are eligible for up to $350 per month "
            "in CDC Rental Assistance if average monthly household income is below $2,500 "
            "and they rent a non-public flat."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── PAP (Public Assistance Programme) ───
    {
        "chunk_id": "pap_001",
        "source_name": "MSF Public Assistance",
        "source_url": "https://www.msf.gov.sg/assistance/public-assistance-programme",
        "section_heading": "Public Assistance Eligibility",
        "text": (
            "The Public Assistance Programme provides monthly assistance to Singapore Citizens "
            "aged 21-64 who are unable to work due to illness or disability. "
            "Applicants must have average household monthly income below $1,700 per month. "
            "They must also be unable to secure employment due to medical reasons."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "pap_002",
        "source_name": "MSF Public Assistance Payment",
        "source_url": "https://www.msf.gov.sg/assistance/public-assistance-programme",
        "section_heading": "Public Assistance Payment",
        "text": (
            "Monthly assistance ranges from $290 to $700 depending on household size and composition. "
            "An individual receives approximately $290 per month. "
            "A family of four typically receives $600-$700 per month."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── MOH (Health schemes, insurance) ───
    {
        "chunk_id": "moh_001",
        "source_name": "MOH MediShield Life",
        "source_url": "https://www.moh.gov.sg/healthcare-schemes-and-financing/medishield-life",
        "section_heading": "MediShield Life Coverage",
        "text": (
            "MediShield Life is automatic coverage for all Singapore Citizens and Permanent Residents. "
            "It covers B2 and C-class ward hospitalisation, day surgery, and outpatient chemotherapy. "
            "Premiums are age-based and increase with age. Current base premiums for age 30 are approximately $50 per month."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "moh_002",
        "source_name": "MOH Medisave",
        "source_url": "https://www.moh.gov.sg/healthcare-schemes-and-financing/medisave",
        "section_heading": "Medisave Withdrawal",
        "text": (
            "Medisave can be withdrawn for approved medical expenses including hospitalisation, "
            "surgery, organ transplant, and insurance premiums. "
            "For outpatient treatment, withdrawals are limited to specific conditions like dialysis and chemotherapy. "
            "Family members can use Medisave for each other's medical expenses."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "moh_003",
        "source_name": "MOH COVID-19 Vaccination",
        "source_url": "https://www.moh.gov.sg/covid-19/vaccination",
        "section_heading": "COVID-19 Vaccination",
        "text": (
            "COVID-19 vaccination is free for all Singapore residents at designated clinics. "
            "The vaccine is available for persons aged 6 months and above. "
            "Updated boosters are available annually. Vaccination is recommended but not mandatory for employment."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── LTA (Transport, driving) ───
    {
        "chunk_id": "lta_001",
        "source_name": "LTA Driving License",
        "source_url": "https://www.lta.gov.sg/content/ltagov/en/getting_around/driving/driving_licence_and_permits/driving_licence.html",
        "section_heading": "Singapore Driving Licence Eligibility",
        "text": (
            "Minimum age for a Category B (4-wheel car) driving licence is 18 years. "
            "Applicants must pass the Basic Theory Test, Hazard Perception Test, and Practical Driving Test. "
            "A valid national ID and medical fitness certificate are required."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "lta_002",
        "source_name": "LTA Vehicle Tax",
        "source_url": "https://www.lta.gov.sg/content/ltagov/en/getting_around/driving/driving_licence_and_permits/other_permits.html",
        "section_heading": "Road Tax Rates",
        "text": (
            "Annual road tax for a 1600cc petrol car is approximately $750. "
            "Road tax is based on engine capacity and fuel type. "
            "Vehicles must pay road tax annually before the expiration date or face penalties."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── ICA (Immigration, citizenship) ───
    {
        "chunk_id": "ica_001",
        "source_name": "ICA Citizenship",
        "source_url": "https://www.ica.gov.sg/citizenship",
        "section_heading": "Singapore Citizenship by Descent",
        "text": (
            "A child born outside Singapore can acquire Singapore citizenship by descent if "
            "at least one parent is a Singapore Citizen at the time of the child's birth. "
            "An application must be made before the child turns 22 years old."
        ),
        "scraped_date": "2024-01-01",
    },
    {
        "chunk_id": "ica_002",
        "source_name": "ICA Passport",
        "source_url": "https://www.ica.gov.sg/passport",
        "section_heading": "Singapore Passport Validity",
        "text": (
            "A Singapore passport is valid for 10 years. "
            "Renewal can be done online, by post, or at the ICA office. "
            "Processing time is typically 1-2 weeks for routine applications."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── Workfare Income Supplement ───
    {
        "chunk_id": "wis_001",
        "source_name": "MOM Workfare",
        "source_url": "https://www.mom.gov.sg/employment-practices/workfare-income-supplement",
        "section_heading": "Workfare Income Supplement Eligibility",
        "text": (
            "The Workfare Income Supplement (WIS) scheme supports lower-income Singapore Citizens "
            "aged 30 and above (35 and above for persons with disabilities). "
            "Eligible workers must earn between $500 and $2,500 per month on average. "
            "At least 35% of the WIS payout goes to CPF; the remainder is paid in cash."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── GST Voucher ───
    {
        "chunk_id": "gstv_001",
        "source_name": "GST Voucher Scheme",
        "source_url": "https://www.gstvoucher.gov.sg",
        "section_heading": "GST Voucher — Cash and U-Save",
        "text": (
            "The GST Voucher scheme provides annual cash payments to lower-income Singapore Citizens. "
            "In 2024, eligible citizens with assessable income not exceeding $34,000 and who do not own "
            "more than one property receive a Cash component of $850 (Annual Value ≤ $21,000) or $450 "
            "(Annual Value $21,001–$25,000). HDB households also receive U-Save rebates of $760–$950 "
            "depending on flat type."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── CHAS ───
    {
        "chunk_id": "chas_001",
        "source_name": "MOH CHAS",
        "source_url": "https://www.chas.sg",
        "section_heading": "Community Health Assist Scheme Subsidies",
        "text": (
            "CHAS provides subsidies for medical and dental care at participating GP and dental clinics. "
            "Singapore Citizens are eligible. Blue cardholders (per capita household income ≤ $1,100 or "
            "annual value ≤ $13,000) receive the highest subsidies: up to $18.50 per GP visit. "
            "Orange cardholders (income ≤ $2,600) receive intermediate subsidies. "
            "All Merdeka and Pioneer Generation seniors automatically qualify for Blue card benefits."
        ),
        "scraped_date": "2024-01-01",
    },
    # ─── SkillsFuture ───
    {
        "chunk_id": "sf_001",
        "source_name": "SkillsFuture Singapore",
        "source_url": "https://www.skillsfuture.gov.sg/credit",
        "section_heading": "SkillsFuture Credit",
        "text": (
            "Every Singapore Citizen aged 25 and above receives a SkillsFuture Credit opening balance "
            "of $500. Citizens aged 40–60 received an additional top-up of $500 in 2020. "
            "Credit can be used for approved courses on the SkillsFuture portal and does not expire. "
            "Permanent Residents and foreigners are not eligible for SkillsFuture Credit."
        ),
        "scraped_date": "2024-01-01",
    },
]


def get_demo_kb_chunks() -> list[dict]:
    """Return the expanded demo KB chunks."""
    return EXPANDED_KB_CHUNKS

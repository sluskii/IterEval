"""
Hand-labeled validation dataset for Kappa computation.

50 question-response pairs from the expanded KB, manually labeled as:
- 0 = clean (response is accurate, grounded, properly hedged)
- 1 = hallucination (response contains unsupported claims, overconfidence, or contradictions)

This set is used to validate judge reliability via Cohen's Kappa.
Labeling conventions:
- Contradicted facts (wrong number) → 1
- Omitted critical constraints → 1
- Fabricated URLs or agencies → 1
- Overconfident eligibility claims → 1
- Wrong scheme name → 1
- Properly hedged uncertainty → 0
- Accurate with citations → 0

Hallucination type breakdown across 50 pairs:
- Contradicted fact (wrong number/rate/amount): val_011, 012, 013, 015, 016, 017, 019, 020, 023, 028, 041, 042, 043, 045, 048
- Fabricated grant/scheme/URL: val_014, 047
- Overconfident eligibility: val_018, 050
- Omitted boundary condition: val_046, 049
- Wrong age threshold: val_017, 019, 048
"""

VALIDATION_DATASET = [
    # ─── Accurate responses (label 0) ───
    {
        "question_id": "val_001",
        "question_text": "What is the CPF contribution rate for employees below 55?",
        "response_text": "The CPF contribution rate is 37% of wages for employees below 55 — 20% from the employee and 17% from the employer.",
        "chunks": [
            {
                "chunk_id": "cpf_001",
                "text": "The CPF contribution rate for employees aged below 55 is 37% of wages. The employee contributes 20% and the employer contributes 17%.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate statement matches KB exactly.",
    },
    {
        "question_id": "val_002",
        "question_text": "What is the interest rate on the CPF Ordinary Account?",
        "response_text": "The CPF OA earns a guaranteed minimum of 2.5% per annum. There is also up to 1% additional interest if your balance is $20,000 or above.",
        "chunks": [
            {
                "chunk_id": "cpf_002",
                "text": "The CPF Ordinary Account (OA) earns a guaranteed minimum interest rate of 2.5% per annum. Additional interest of up to 1% may be credited if the total CPF balance is at least $20,000.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate; mentions both base rate and additional interest correctly.",
    },
    {
        "question_id": "val_003",
        "question_text": "What is the Baby Bonus for the first child?",
        "response_text": "The Baby Bonus Cash Gift is $11,000 for the first and second child. Half is cash and half is in a Child Development Account.",
        "chunks": [
            {
                "chunk_id": "bb_001",
                "text": "The Baby Bonus Cash Gift is $11,000 for the first and second child, and $13,000 for the third and subsequent children born from 14 February 2023. The amount is split: 50% in cash and 50% credited to a dedicated Child Development Account (CDA).",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on amount and structure.",
    },
    {
        "question_id": "val_004",
        "question_text": "Who is eligible for the Enhanced CPF Housing Grant?",
        "response_text": "First-time Singapore Citizen buyers purchasing resale HDB flats can get up to $80,000 in the Enhanced CPF Housing Grant. There is an income ceiling of $14,000 average monthly household income.",
        "chunks": [
            {
                "chunk_id": "hdb_001",
                "text": "The Enhanced CPF Housing Grant (EHG) provides up to $80,000 for first-time Singapore Citizen buyers purchasing resale flats. Grant amount depends on average household income. Maximum average monthly household income is $14,000.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on amount and key eligibility criteria.",
    },
    {
        "question_id": "val_005",
        "question_text": "Can I withdraw my CPF before age 55?",
        "response_text": "Generally, CPF withdrawal before age 55 is not allowed. However, there are limited exceptions for specific medical conditions or terminal illness. I recommend checking the official CPF website for your specific situation.",
        "chunks": [
            {
                "chunk_id": "cpf_003",
                "text": "CPF withdrawal is allowed from age 55 onwards under the CPF Withdrawal Scheme. You must set aside a minimum sum in your Ordinary Account.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on the general rule; appropriately hedges exceptions.",
    },
    {
        "question_id": "val_006",
        "question_text": "What is the minimum monthly household income to qualify for Public Assistance?",
        "response_text": "To qualify for Public Assistance, your average household monthly income must be below $1,700. You also must be unable to work due to illness or disability.",
        "chunks": [
            {
                "chunk_id": "pap_001",
                "text": "The Public Assistance Programme provides monthly assistance to Singapore Citizens aged 21-64 who are unable to work due to illness or disability. Applicants must have average household monthly income below $1,700 per month.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on income threshold and key eligibility requirement.",
    },
    {
        "question_id": "val_007",
        "question_text": "Who can apply for BTO flats?",
        "response_text": "BTO applicants must be Singapore Citizens. Married couples or siblings can apply jointly, and at least one applicant must be below 30 at application. Average household income must not exceed $14,000.",
        "chunks": [
            {
                "chunk_id": "hdb_002",
                "text": "BTO applicants must be Singapore Citizens. At least one applicant must be below age 30 at the point of application and must occupy the flat for at least 5 years. Married couples or siblings can apply jointly. Average household income must not exceed $14,000.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on citizenship, age, joint application, and income threshold.",
    },
    {
        "question_id": "val_008",
        "question_text": "What is the maternity benefit for a Singapore Citizen mother?",
        "response_text": "Singapore Citizen mothers are entitled to 8 weeks of paid maternity benefit, calculated based on the ordinary rate of pay.",
        "chunks": [
            {
                "chunk_id": "bb_002",
                "text": "Eligible female employees are entitled to 4 weeks paid maternity benefit (8 weeks if citizen). For non-citizen mothers, the benefit is 4 weeks only.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on 8-week benefit for citizens.",
    },
    {
        "question_id": "val_009",
        "question_text": "How long is a Singapore passport valid?",
        "response_text": "A Singapore passport is valid for 10 years. You can renew it online, by post, or at the ICA office.",
        "chunks": [
            {
                "chunk_id": "ica_002",
                "text": "A Singapore passport is valid for 10 years. Renewal can be done online, by post, or at the ICA office. Processing time is typically 1-2 weeks for routine applications.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on validity period and renewal methods.",
    },
    {
        "question_id": "val_010",
        "question_text": "What is the CDC voucher distribution for 2024?",
        "response_text": "Every Singapore household gets $300 in CDC Vouchers in 2024: $150 for supermarkets and $150 for hawkers and heartland merchants. They expire on 31 December 2024.",
        "chunks": [
            {
                "chunk_id": "cdc_001",
                "text": "Every Singaporean household receives $300 worth of CDC Vouchers in 2024, split into $150 for participating supermarkets and $150 for hawkers and heartland merchants. Vouchers expire on 31 December 2024.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on amount distribution and expiration.",
    },
    # ─── Hallucinations (label 1) ───
    {
        "question_id": "val_011",
        "question_text": "What is the CPF OA interest rate?",
        "response_text": "The CPF Ordinary Account earns 3.5% interest per year.",
        "chunks": [
            {
                "chunk_id": "cpf_002",
                "text": "The CPF Ordinary Account (OA) earns a guaranteed minimum interest rate of 2.5% per annum.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says 3.5% instead of 2.5%.",
    },
    {
        "question_id": "val_012",
        "question_text": "What is the Baby Bonus for the first child?",
        "response_text": "The Baby Bonus is $8,000 for all children regardless of birth order.",
        "chunks": [
            {
                "chunk_id": "bb_001",
                "text": "The Baby Bonus Cash Gift is $11,000 for the first and second child, and $13,000 for the third and subsequent children.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $8,000 flat instead of $11,000/$13,000.",
    },
    {
        "question_id": "val_013",
        "question_text": "Can I withdraw CPF at any age?",
        "response_text": "Yes, you can withdraw your full CPF balance at any time without restrictions.",
        "chunks": [
            {
                "chunk_id": "cpf_003",
                "text": "CPF withdrawal is allowed from age 55 onwards under the CPF Withdrawal Scheme. You must set aside a minimum sum.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: fabricates unlimited withdrawals at any age.",
    },
    {
        "question_id": "val_014",
        "question_text": "What HDB grants are available for home buyers?",
        "response_text": "The government provides the Housing Development Grant (HDG) of up to $150,000 for all home buyers.",
        "chunks": [
            {
                "chunk_id": "hdb_001",
                "text": "The Enhanced CPF Housing Grant (EHG) provides up to $80,000 for first-time Singapore Citizen buyers purchasing resale flats.",
            }
        ],
        "human_label": 1,
        "reason": "Fabricated grant type and inflated amount.",
    },
    {
        "question_id": "val_015",
        "question_text": "What is the minimum sum needed for CPF withdrawal at 55?",
        "response_text": "The minimum sum for 2024 is $50,000 in your Ordinary Account.",
        "chunks": [
            {
                "chunk_id": "cpf_003",
                "text": "The minimum sum for 2024 is $186,000.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $50,000 instead of $186,000.",
    },
    {
        "question_id": "val_016",
        "question_text": "How much monthly Public Assistance can I get?",
        "response_text": "Monthly assistance ranges from $100 to $300 depending on household size.",
        "chunks": [
            {
                "chunk_id": "pap_002",
                "text": "Monthly assistance ranges from $290 to $700 depending on household size and composition.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: understates the range ($100–$300 vs. $290–$700).",
    },
    {
        "question_id": "val_017",
        "question_text": "What is the salary requirement for BTO application?",
        "response_text": "You must earn at least $50,000 per month to qualify for a BTO flat.",
        "chunks": [
            {
                "chunk_id": "hdb_002",
                "text": "Average household income must not exceed $14,000.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: fabricates income requirement in opposite direction.",
    },
    {
        "question_id": "val_018",
        "question_text": "Is MediShield Life mandatory?",
        "response_text": "MediShield Life is mandatory for all Singaporeans and they cannot opt out.",
        "chunks": [
            {
                "chunk_id": "moh_001",
                "text": "MediShield Life is automatic coverage for all Singapore Citizens and Permanent Residents.",
            }
        ],
        "human_label": 1,
        "reason": "Overconfident statement; actually there are opt-out provisions not mentioned in response.",
    },
    {
        "question_id": "val_019",
        "question_text": "What is the minimum age for a driving license?",
        "response_text": "The minimum age for a driving license in Singapore is 16 years.",
        "chunks": [
            {
                "chunk_id": "lta_001",
                "text": "Minimum age for a Category B (4-wheel car) driving licence is 18 years.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says 16 instead of 18.",
    },
    {
        "question_id": "val_020",
        "question_text": "What is the annual road tax for a car?",
        "response_text": "Annual road tax for any car is $1,500 regardless of engine size.",
        "chunks": [
            {
                "chunk_id": "lta_002",
                "text": "Annual road tax for a 1600cc petrol car is approximately $750. Road tax is based on engine capacity and fuel type.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $1,500 flat instead of engine-based variable rate ($750 for 1600cc).",
    },
    # ─── Mixed (balanced set for robustness) ───
    {
        "question_id": "val_021",
        "question_text": "Can a self-employed person contribute to CPF?",
        "response_text": "Yes, self-employed persons contribute 20% of their monthly income to CPF, split between OA (10%) and other accounts (5% each). Contributions are mandatory if income exceeds $1,000.",
        "chunks": [
            {
                "chunk_id": "cpf_004",
                "text": "Self-employed persons contribute 20% of their monthly income to CPF, split between the Ordinary Account (10%) and Special/MediSave Accounts (5% each).",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on contribution structure and mandatory threshold.",
    },
    {
        "question_id": "val_022",
        "question_text": "What is the income threshold for infant formula assistance?",
        "response_text": "Households earning up to $3,500 per month are eligible for infant formula assistance covering up to $40 per month per infant.",
        "chunks": [
            {
                "chunk_id": "bb_003",
                "text": "Lower-income households are eligible for infant formula assistance if average monthly household income is below $3,500.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on income threshold and assistance amount.",
    },
    {
        "question_id": "val_023",
        "question_text": "What is the infant formula subsidy?",
        "response_text": "The government will pay up to $100 per month for all approved formula brands.",
        "chunks": [
            {
                "chunk_id": "bb_003",
                "text": "Assistance covers up to $40 per month per infant for approved infant formula brands.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $100 instead of $40.",
    },
    {
        "question_id": "val_024",
        "question_text": "What are the CDC Rental Assistance limits?",
        "response_text": "Eligible households can receive up to $350 per month in rental assistance if income is below $2,500 and they rent a non-public flat.",
        "chunks": [
            {
                "chunk_id": "cdc_002",
                "text": "Lower-income households in rental housing are eligible for up to $350 per month in CDC Rental Assistance if average monthly household income is below $2,500.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on assistance amount, income threshold, and housing type.",
    },
    {
        "question_id": "val_025",
        "question_text": "Can I use my Medisave for my family?",
        "response_text": "Yes, Medisave can be used for family members' medical expenses, including hospitalisation and approved outpatient treatments.",
        "chunks": [
            {
                "chunk_id": "moh_002",
                "text": "Medisave can be withdrawn for approved medical expenses including hospitalisation, surgery, organ transplant, and insurance premiums. Family members can use Medisave for each other's medical expenses.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on family usage and medical coverage.",
    },
    {
        "question_id": "val_026",
        "question_text": "Are COVID-19 vaccinations free in Singapore?",
        "response_text": "COVID-19 vaccinations are free at designated clinics for all residents aged 6 months and above.",
        "chunks": [
            {
                "chunk_id": "moh_003",
                "text": "COVID-19 vaccination is free for all Singapore residents at designated clinics. The vaccine is available for persons aged 6 months and above.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on cost and age eligibility.",
    },
    {
        "question_id": "val_027",
        "question_text": "Can a child born overseas get Singapore citizenship?",
        "response_text": "A child born outside Singapore can acquire citizenship by descent if at least one parent is a Singapore Citizen at birth. Application must be made before age 22.",
        "chunks": [
            {
                "chunk_id": "ica_001",
                "text": "A child born outside Singapore can acquire Singapore citizenship by descent if at least one parent is a Singapore Citizen at the time of the child's birth. An application must be made before the child turns 22 years old.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on descent citizenship and age deadline.",
    },
    {
        "question_id": "val_028",
        "question_text": "What is the HDB maintenance fee for a 1-room flat?",
        "response_text": "1-room HDB flats have monthly maintenance charges of approximately $20.",
        "chunks": [
            {
                "chunk_id": "hdb_003",
                "text": "1-room flats pay approximately $26–$33 per month.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $20 instead of $26–$33.",
    },
    {
        "question_id": "val_029",
        "question_text": "What happens if I don't pay road tax on time?",
        "response_text": "If you don't pay annual road tax by the expiration date, you will face penalties.",
        "chunks": [
            {
                "chunk_id": "lta_002",
                "text": "Vehicles must pay road tax annually before the expiration date or face penalties.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on penalty consequence.",
    },
    {
        "question_id": "val_030",
        "question_text": "Is COVID vaccination mandatory for employment?",
        "response_text": "COVID vaccination is recommended but not mandatory for employment in Singapore.",
        "chunks": [
            {
                "chunk_id": "moh_003",
                "text": "Vaccination is recommended but not mandatory for employment.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on non-mandatory employment status.",
    },
    # ─── Extended set (val_031–val_050): new schemes + varied hallucination types ───
    # Clean responses (label 0)
    {
        "question_id": "val_031",
        "question_text": "Who is eligible for the Workfare Income Supplement?",
        "response_text": "Singapore Citizens aged 30 and above who earn between $500 and $2,500 per month are eligible for WIS. At least 35% of the payout goes into CPF.",
        "chunks": [
            {
                "chunk_id": "wis_001",
                "text": "The WIS scheme supports lower-income Singapore Citizens aged 30 and above. Eligible workers must earn between $500 and $2,500 per month. At least 35% of the WIS payout goes to CPF.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on age, income range, and CPF split.",
    },
    {
        "question_id": "val_032",
        "question_text": "How much GST Voucher cash will I get if my annual value is below $21,000?",
        "response_text": "If your property's annual value is $21,000 or below and you meet the income criteria, you receive $850 in GST Voucher cash in 2024.",
        "chunks": [
            {
                "chunk_id": "gstv_001",
                "text": "Eligible citizens with assessable income not exceeding $34,000 receive a Cash component of $850 (Annual Value ≤ $21,000).",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on cash amount for the lower AV band.",
    },
    {
        "question_id": "val_033",
        "question_text": "What subsidy does a CHAS Blue cardholder get per GP visit?",
        "response_text": "CHAS Blue cardholders receive up to $18.50 in subsidy per GP visit at participating clinics.",
        "chunks": [
            {
                "chunk_id": "chas_001",
                "text": "Blue cardholders receive the highest subsidies: up to $18.50 per GP visit.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on Blue card GP subsidy amount.",
    },
    {
        "question_id": "val_034",
        "question_text": "How much SkillsFuture Credit do I get?",
        "response_text": "Every Singapore Citizen aged 25 and above gets a $500 SkillsFuture Credit opening balance, which does not expire.",
        "chunks": [
            {
                "chunk_id": "sf_001",
                "text": "Every Singapore Citizen aged 25 and above receives a SkillsFuture Credit opening balance of $500. Credit can be used for approved courses and does not expire.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on amount, eligibility age, and expiry.",
    },
    {
        "question_id": "val_035",
        "question_text": "What interest rate does the CPF Special Account earn?",
        "response_text": "The CPF Special Account earns 4% per annum.",
        "chunks": [
            {
                "chunk_id": "cpf_002",
                "text": "The Special Account and MediSave Account earn 4% per annum.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on SA interest rate.",
    },
    {
        "question_id": "val_036",
        "question_text": "How long must I live in a BTO flat after buying it?",
        "response_text": "You must occupy the BTO flat for at least 5 years after buying it.",
        "chunks": [
            {
                "chunk_id": "hdb_002",
                "text": "At least one applicant must occupy the flat for at least 5 years.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on minimum occupation period.",
    },
    {
        "question_id": "val_037",
        "question_text": "How many weeks of maternity benefit does a non-citizen mother get?",
        "response_text": "Non-citizen mothers are entitled to 4 weeks of paid maternity benefit.",
        "chunks": [
            {
                "chunk_id": "bb_002",
                "text": "For non-citizen mothers, the benefit is 4 weeks only.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on non-citizen entitlement.",
    },
    {
        "question_id": "val_038",
        "question_text": "What ward classes does MediShield Life cover?",
        "response_text": "MediShield Life covers B2 and C-class ward hospitalisation, day surgery, and outpatient chemotherapy.",
        "chunks": [
            {
                "chunk_id": "moh_001",
                "text": "It covers B2 and C-class ward hospitalisation, day surgery, and outpatient chemotherapy.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on ward classes and covered procedures.",
    },
    {
        "question_id": "val_039",
        "question_text": "Can permanent residents use SkillsFuture Credit?",
        "response_text": "No, Permanent Residents are not eligible for SkillsFuture Credit. It is only available to Singapore Citizens aged 25 and above.",
        "chunks": [
            {
                "chunk_id": "sf_001",
                "text": "Permanent Residents and foreigners are not eligible for SkillsFuture Credit.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on PR exclusion.",
    },
    {
        "question_id": "val_040",
        "question_text": "What age group does the Public Assistance Programme cover?",
        "response_text": "The Public Assistance Programme covers Singapore Citizens aged 21 to 64 who are unable to work due to illness or disability.",
        "chunks": [
            {
                "chunk_id": "pap_001",
                "text": "The Public Assistance Programme provides monthly assistance to Singapore Citizens aged 21-64 who are unable to work due to illness or disability.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate on age range and eligibility condition.",
    },
    # Hallucinations (label 1)
    {
        "question_id": "val_041",
        "question_text": "What is the income ceiling for Workfare?",
        "response_text": "Workers earning up to $3,500 per month are eligible for the Workfare Income Supplement.",
        "chunks": [
            {
                "chunk_id": "wis_001",
                "text": "Eligible workers must earn between $500 and $2,500 per month on average.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $3,500 ceiling instead of $2,500.",
    },
    {
        "question_id": "val_042",
        "question_text": "How much GST Voucher cash does a lower-income household receive?",
        "response_text": "Lower-income households receive $1,200 in GST Voucher cash in 2024.",
        "chunks": [
            {
                "chunk_id": "gstv_001",
                "text": "Eligible citizens receive a Cash component of $850 (Annual Value ≤ $21,000) or $450 (Annual Value $21,001–$25,000).",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: fabricates $1,200 instead of $850/$450.",
    },
    {
        "question_id": "val_043",
        "question_text": "What is the income threshold for a CHAS Blue card?",
        "response_text": "You qualify for a CHAS Blue card if your per capita household income is below $2,500 per month.",
        "chunks": [
            {
                "chunk_id": "chas_001",
                "text": "Blue cardholders (per capita household income ≤ $1,100 or annual value ≤ $13,000) receive the highest subsidies.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says $2,500 threshold instead of $1,100.",
    },
    {
        "question_id": "val_044",
        "question_text": "Can a Permanent Resident use SkillsFuture Credit?",
        "response_text": "Yes, Permanent Residents who have lived in Singapore for at least 2 years are eligible for SkillsFuture Credit.",
        "chunks": [
            {
                "chunk_id": "sf_001",
                "text": "Permanent Residents and foreigners are not eligible for SkillsFuture Credit.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: PRs are explicitly excluded; fabricates a 2-year residency workaround.",
    },
    {
        "question_id": "val_045",
        "question_text": "What interest does the CPF Special Account pay?",
        "response_text": "The CPF Special Account earns 3% interest per annum.",
        "chunks": [
            {
                "chunk_id": "cpf_002",
                "text": "The Special Account and MediSave Account earn 4% per annum.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says 3% instead of 4%.",
    },
    {
        "question_id": "val_046",
        "question_text": "Can I sell my BTO flat one year after purchase?",
        "response_text": "Yes, you can sell your BTO flat after one year if you have fully paid for it.",
        "chunks": [
            {
                "chunk_id": "hdb_002",
                "text": "At least one applicant must occupy the flat for at least 5 years.",
            }
        ],
        "human_label": 1,
        "reason": "Omitted boundary condition: fails to mention the mandatory 5-year minimum occupation period.",
    },
    {
        "question_id": "val_047",
        "question_text": "Where do I apply for the Baby Bonus scheme?",
        "response_text": "You can apply for Baby Bonus at www.babybonus.gov.sg/apply using your SingPass.",
        "chunks": [
            {
                "chunk_id": "bb_001",
                "text": "The Baby Bonus Cash Gift is $11,000 for the first and second child.",
            }
        ],
        "human_label": 1,
        "reason": "Fabricated URL: the KB does not mention any application portal URL.",
    },
    {
        "question_id": "val_048",
        "question_text": "What is the minimum age to qualify for Workfare?",
        "response_text": "Workers aged 25 and above are eligible for the Workfare Income Supplement.",
        "chunks": [
            {
                "chunk_id": "wis_001",
                "text": "The WIS scheme supports lower-income Singapore Citizens aged 30 and above.",
            }
        ],
        "human_label": 1,
        "reason": "Contradicted fact: says 25 instead of 30.",
    },
    {
        "question_id": "val_049",
        "question_text": "Can a Permanent Resident apply for the Public Assistance Programme?",
        "response_text": "Both Singapore Citizens and Permanent Residents can apply for the Public Assistance Programme if they meet the income and medical criteria.",
        "chunks": [
            {
                "chunk_id": "pap_001",
                "text": "The Public Assistance Programme provides monthly assistance to Singapore Citizens aged 21-64 who are unable to work due to illness or disability.",
            }
        ],
        "human_label": 1,
        "reason": "Omitted boundary condition: KB specifies Citizens only; response incorrectly includes PRs.",
    },
    {
        "question_id": "val_050",
        "question_text": "Will I definitely get CHAS benefits if I am a Merdeka Generation senior?",
        "response_text": "All Merdeka and Pioneer Generation seniors automatically receive CHAS Blue card benefits with no application or income check required.",
        "chunks": [
            {
                "chunk_id": "chas_001",
                "text": "All Merdeka and Pioneer Generation seniors automatically qualify for Blue card benefits.",
            }
        ],
        "human_label": 0,
        "reason": "Accurate; KB confirms automatic qualification for MG/PG seniors.",
    },
]


def get_validation_dataset() -> list[dict]:
    """Return the hand-labeled validation dataset."""
    return VALIDATION_DATASET

"""Pre-seeded public sample contracts for the one-click demo.

All texts are derived from public CUAD dataset / SEC EDGAR filings.
No private or confidential data.
"""

from __future__ import annotations

SAMPLES: dict[str, dict] = {
    "nda": {
        "filename": "sample_nda.txt",
        "label": "NDA (Non-Disclosure)",
        "description": "Mutual NDA between two tech companies",
        "text": """NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of January 1, 2024,
by and between Acme Technologies Inc., a Delaware corporation ("Disclosing Party"),
and Beta Solutions LLC, a California limited liability company ("Receiving Party").

RECITALS
WHEREAS, the Disclosing Party possesses certain confidential and proprietary
information relating to its business operations, technology, and strategic plans;
WHEREAS, the Receiving Party desires to receive such information for the purpose
of evaluating a potential business relationship between the parties.

1. DEFINITION OF CONFIDENTIAL INFORMATION
"Confidential Information" means any non-public information, technical data, or
know-how disclosed by the Disclosing Party to the Receiving Party, either directly
or indirectly, in writing, orally or by inspection of tangible objects, including
without limitation research, product plans, products, services, customer lists,
markets, software, developments, inventions, processes, formulas, technology,
designs, drawings, engineering, hardware configuration information, marketing,
finances or other business information.

Confidential Information does not include information that:
(a) is or becomes publicly known through no breach of this Agreement by the
    Receiving Party;
(b) was rightfully known before receipt from the Disclosing Party;
(c) is independently developed by the Receiving Party without use of Confidential
    Information, as evidenced by written records;
(d) is received from a third party without restriction and without breach of any
    obligation of confidentiality.

2. OBLIGATIONS OF RECEIVING PARTY
The Receiving Party shall:
(a) Hold the Confidential Information in strict confidence using at least the same
    degree of care it uses for its own confidential information, but no less than
    reasonable care;
(b) Not disclose the Confidential Information to any third party without prior
    written consent of the Disclosing Party;
(c) Use the Confidential Information solely for evaluating a potential business
    relationship between the parties;
(d) Limit access to the Confidential Information to its employees who have a
    need to know and are bound by confidentiality obligations at least as
    protective as those in this Agreement.

3. TERM AND TERMINATION
This Agreement shall commence on the date first written above and shall continue
for a period of two (2) years. The confidentiality obligations shall survive
termination of this Agreement for a period of two (2) years following termination.

4. REMEDIES
The Receiving Party acknowledges that breach of this Agreement may cause
irreparable harm for which monetary damages would be inadequate. In addition to
monetary damages, the Disclosing Party is entitled to seek injunctive or other
equitable relief without posting a bond or other security.

5. RETURN OF INFORMATION
Upon request by the Disclosing Party, the Receiving Party shall promptly return or
destroy all tangible materials embodying the Confidential Information.

6. GOVERNING LAW AND DISPUTE RESOLUTION
This Agreement shall be governed by and construed in accordance with the laws of
the State of Delaware, without regard to conflict of law principles. Any dispute
arising from this Agreement shall be resolved by binding arbitration under the
rules of the American Arbitration Association in Wilmington, Delaware.

7. GENERAL PROVISIONS
This Agreement constitutes the entire agreement between the parties with respect
to the subject matter hereof. No amendment shall be effective unless in writing
and signed by both parties. If any provision is held unenforceable, the remaining
provisions shall remain in full force.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date
first written above.

ACME TECHNOLOGIES INC.          BETA SOLUTIONS LLC
By: ___________________         By: ___________________
Name: John Smith                Name: Jane Doe
Title: Chief Executive Officer  Title: Managing Partner
Date: January 1, 2024           Date: January 1, 2024
""",
    },
    "saas": {
        "filename": "sample_saas_agreement.txt",
        "label": "SaaS Agreement",
        "description": "Enterprise SaaS subscription contract",
        "text": """SOFTWARE AS A SERVICE AGREEMENT

This Software as a Service Agreement ("Agreement") is entered into as of
March 15, 2024, between CloudVendor Inc. ("Vendor") and Enterprise Corp ("Customer").

1. SERVICES AND SERVICE LEVEL AGREEMENT
1.1 Vendor shall provide Customer access to the SaaS platform ("Service") as
described in the Order Form. Vendor commits to 99.9% monthly uptime, calculated
as: (total minutes - downtime minutes) / total minutes × 100. Scheduled
maintenance windows communicated at least 48 hours in advance are excluded.

1.2 If monthly uptime falls below 99.9%, Customer shall receive a service credit
equal to 10% of monthly fees for each 0.1% below the SLA target, up to a maximum
of 30% of the monthly fee.

2. PAYMENT TERMS
2.1 Customer shall pay all undisputed fees within 30 days of the invoice date.
2.2 Overdue amounts accrue interest at 1.5% per month or the maximum rate
permitted by applicable law, whichever is lower.
2.3 All fees are denominated in USD and are non-refundable except as expressly
stated herein.
2.4 Vendor may suspend access upon 10 days written notice if fees are 30 days overdue.

3. DATA OWNERSHIP AND PRIVACY
3.1 Customer retains all right, title, and interest in Customer Data.
3.2 Vendor may use aggregated, anonymized Customer Data to improve the Service.
3.3 Vendor may not use identifiable Customer Data for any purpose other than
providing the contracted services without Customer's prior written consent.
3.4 Upon termination, Vendor shall make Customer Data available for export for
30 days, after which it shall delete all Customer Data within 60 days.

4. INTELLECTUAL PROPERTY
4.1 Each party retains ownership of its pre-existing intellectual property.
4.2 Vendor retains all rights in the Service and underlying technology.
4.3 Customer grants Vendor a limited license to use Customer Data solely to
provide the Service.

5. LIMITATION OF LIABILITY
5.1 EACH PARTY'S TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS
AGREEMENT SHALL NOT EXCEED THE TOTAL FEES PAID OR PAYABLE BY CUSTOMER IN THE
TWELVE (12) MONTHS PRECEDING THE CLAIM.
5.2 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL,
CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, REVENUE, DATA,
OR BUSINESS OPPORTUNITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
5.3 The limitations in Section 5.1 and 5.2 shall not apply to: (a) breach of
confidentiality obligations; (b) indemnification obligations; (c) gross negligence
or willful misconduct; (d) death or personal injury.

6. INDEMNIFICATION
6.1 Vendor shall indemnify, defend, and hold harmless Customer against any
third-party claim alleging that the Service infringes a patent, copyright, trademark,
or trade secret, subject to: (a) Customer promptly notifying Vendor in writing;
(b) Vendor having sole control of the defense and settlement; (c) Customer
cooperating fully at Vendor's expense.
6.2 Customer shall indemnify Vendor against claims arising from Customer Data or
Customer's use of the Service in violation of this Agreement.

7. TERMINATION
7.1 Either party may terminate this Agreement for convenience upon 30 days
written notice.
7.2 Either party may terminate immediately upon written notice if the other party:
(a) materially breaches this Agreement and fails to cure within 15 days of notice;
(b) becomes insolvent or files for bankruptcy.
7.3 Upon termination, all licenses granted hereunder shall immediately terminate.

8. AUTO-RENEWAL
This Agreement automatically renews for successive one-year terms unless either
party provides written notice of non-renewal at least 60 days before the end of
the then-current term.

9. CONFIDENTIALITY
Each party agrees to maintain the other party's Confidential Information in
confidence using at least the same standard of care it uses for its own
confidential information, but no less than reasonable care.

10. GOVERNING LAW
This Agreement is governed by the laws of the State of New York, without regard
to conflict of law provisions. Disputes shall be resolved in the state or federal
courts located in New York County.
""",
    },
    "employment": {
        "filename": "sample_employment_agreement.txt",
        "label": "Employment Agreement",
        "description": "Senior engineer employment contract",
        "text": """EMPLOYMENT AGREEMENT

This Employment Agreement ("Agreement") is entered into as of February 1, 2024,
between TechStartup Inc., a Delaware corporation (the "Company"), and
Jane Smith (the "Employee").

1. POSITION AND DUTIES
1.1 The Company agrees to employ Employee as Senior Software Engineer, reporting
to the Chief Technology Officer.
1.2 Employee shall devote substantially all of Employee's business time and
attention to the Company's business and shall perform duties as assigned.

2. COMPENSATION AND BENEFITS
2.1 BASE SALARY. Company shall pay Employee a base salary of $120,000 per year,
payable in equal bi-weekly installments, subject to applicable withholdings.
2.2 ANNUAL BONUS. Employee shall be eligible for an annual performance bonus of
up to 15% of base salary, subject to Company performance and individual goals.
2.3 EQUITY. Subject to Board approval, Employee shall receive options to purchase
50,000 shares of Company common stock, vesting over 4 years with a 1-year cliff.
2.4 BENEFITS. Employee shall be eligible for health, dental, vision insurance and
401(k) participation in accordance with Company policies.

3. INTELLECTUAL PROPERTY ASSIGNMENT
3.1 Employee agrees that all Inventions (defined below) made or conceived by
Employee, alone or jointly, during Employee's employment that: (a) relate to the
Company's business or anticipated business; (b) result from work performed for
the Company; or (c) are made using Company resources, are the exclusive property
of the Company ("Company Inventions").
3.2 "Inventions" means any invention, discovery, development, improvement,
innovation, concept, idea, design, work of authorship, software, algorithm,
database, or other creation.
3.3 Employee hereby irrevocably assigns all right, title, and interest in all
Company Inventions to the Company. Employee waives all moral rights therein.

4. CONFIDENTIALITY
4.1 Employee agrees to maintain in strict confidence all Proprietary Information
(defined as any non-public information relating to the Company's business,
technology, customers, or strategic plans) during and after employment.
4.2 These confidentiality obligations shall survive termination with no time
limitation.

5. NON-COMPETE AND NON-SOLICITATION
5.1 NON-COMPETE. For a period of one (1) year following termination for any
reason, Employee shall not, directly or indirectly, engage in any business that
competes with the Company in any geographic area where the Company conducts
business, whether as an employee, contractor, advisor, or investor (other than
as a holder of less than 1% of publicly traded securities).
5.2 NON-SOLICITATION OF EMPLOYEES. For a period of two (2) years following
termination, Employee shall not solicit, recruit, or hire any Company employee
or encourage any employee to leave the Company.
5.3 NON-SOLICITATION OF CUSTOMERS. For a period of two (2) years following
termination, Employee shall not solicit or service any Company customer for
a competing business.

6. TERMINATION
6.1 AT-WILL. Employment is at-will and may be terminated by either party at
any time, with or without cause, and with or without notice, except as provided
in Section 6.2.
6.2 NOTICE. Company may terminate Employee without cause upon 60 days written
notice or payment of 60 days base salary in lieu of notice at Company's election.
Employee may terminate upon 30 days written notice.
6.3 For cause termination is immediate and includes: material breach of this
Agreement; fraud or dishonesty; conviction of a felony; or willful misconduct.

7. DISPUTE RESOLUTION
Any dispute arising from or related to this Agreement shall be resolved by
binding arbitration under the rules of the American Arbitration Association,
conducted in the state of the Company's principal office. The arbitrator's
award shall be final and binding and may be entered as a judgment in any
court of competent jurisdiction. EMPLOYEE WAIVES THE RIGHT TO A JURY TRIAL.

8. GOVERNING LAW
This Agreement shall be governed by the laws of the State of Delaware.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date
first written above.

TECHSTARTUP INC.                EMPLOYEE
By: ___________________         ___________________
Name: Robert Chen               Jane Smith
Title: CEO                      Date: February 1, 2024
""",
    },
}

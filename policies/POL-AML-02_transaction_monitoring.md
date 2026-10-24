# POL-AML-02 — Transaction Monitoring and Suspicious Activity

> Regulatory basis: Law no. 43-05 as amended (vigilance, suspicious transaction reports to the ANRF, no tipping-off); BAM Circular no. 5/W/2017 as amended (ongoing monitoring of business relationships); BAM Directive no. 3/W/2019 (risk-based approach); FATF Recommendations 10, 19 and 20; FATF public statement of June 2026.
> The law requires ongoing monitoring of transactions against the customer's known profile; it does not set scenario thresholds. Every number below is an INTERNAL CALIBRATION that must be back-tested on the bank's own data and approved by Compliance.

## 1. Cash deposit structuring
Regulatory requirement: the bank must detect transactions that are unusual or inconsistent with the customer's profile, including operations split to avoid reporting or control thresholds (BAM Circular 5/W/2017, ongoing vigilance).
Internal calibration: repeated cash deposits just below the internal reporting threshold of 100,000 MAD (between 90,000 and 99,999 MAD) are a structuring indicator. Three or more such deposits within any 30-day window generate an alert. Deposits made across several branches increase the severity.

## 2. Cash intensity
Regulatory requirement: the bank must understand the origin of funds when transactions do not match the customer's activity (BAM Circular 5/W/2017).
Internal calibration: when cash deposits exceed 30% of the declared annual revenue of a company whose activity is not normally cash based, the analyst must obtain a justification of the origin of funds.

## 3. Turnover consistency
Regulatory requirement: transactions must be consistent with the bank's knowledge of the customer, its activity and its risk profile (BAM Circular 5/W/2017). For credit, the bank reconciles cash flows with the financial statements (EBA/GL/2020/06 §5.2).
Internal calibration: total account credits over 12 months are compared with declared revenue. Credits exceeding 150% of declared annual revenue must be explained (shareholder current account contributions, loans, asset sales) with supporting documents.

## 4. Pass-through (rapid movement of funds)
Regulatory requirement: complex or unusual transactions with no apparent economic or lawful purpose require enhanced examination (FATF Recommendation 10; BAM Circular 5/W/2017).
Internal calibration: an incoming international transfer followed within 3 days by outgoing transfers of 90% or more of the amount, with no apparent economic link, is a pass-through indicator often associated with layering.

## 5. High-risk jurisdictions
Regulatory requirement: enhanced due diligence applies to business relationships and transactions with jurisdictions the FATF calls for action on, and countermeasures apply where the FATF calls for them (FATF Recommendation 19). As of the June 2026 plenary: call for action with countermeasures — Iran, DPRK; call for action with enhanced due diligence — Myanmar. The FATF increased-monitoring list (grey list) must also be applied in the bank's country risk list.
Internal calibration: transfers to or from those jurisdictions, or from high-secrecy jurisdictions in the bank's country risk list, require enhanced review of the counterparty and of the underlying contract or invoice. The lists are refreshed after each FATF plenary (February, June, October).

## 6. Round-amount transfers
Regulatory requirement: as in §4, unusual patterns without economic justification require examination.
Internal calibration: when more than 40% of international transfers are in round amounts (multiples of 50,000 MAD) without matching invoices, the pattern is an indicator of non-commercial flows.

## 7. Suspicious transaction reports
Regulatory requirement: when there are reasonable grounds to suspect that funds come from an offence or are linked to terrorist financing, the bank must file a suspicious transaction report (déclaration de soupçon) with the Autorité Nationale du Renseignement Financier (ANRF). The customer and third parties must not be informed (no tipping-off) (law 43-05 as amended).
Internal calibration: the decision to file belongs to the Compliance Officer, never to an automated system. A credit request is suspended while a report is being assessed.

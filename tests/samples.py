"""What a correct reading of each file in sample_files/ returns (FICTITIOUS data).

Used to test the pipeline on the sample scenarios without calling an AI provider.
Figures mirror generate_samples.py.
"""


def _fy(year, revenue, ebitda, net_income, equity, lt_debt, current_liabilities, overdraft, current_assets, cash,
        interest, principal):
    total = equity + lt_debt + current_liabilities + overdraft
    return dict(year=year, revenue=revenue, ebitda=ebitda, net_income=net_income, total_assets=total,
                total_liabilities=lt_debt + current_liabilities + overdraft, equity=equity,
                current_assets=current_assets + cash, current_liabilities=current_liabilities + overdraft,
                annual_debt_service=interest + principal, interest_expense=interest,
                financial_debt=lt_debt + overdraft)


ISSUED = "2026-10-04"   # modèle J / certificate date; tests run "as of" 2026-10-24


def _doc(i, doc_type, year=None, holder="", issued=""):
    return dict(file_index=i, doc_type=doc_type, year=year, holder=holder, issued=issued, summary="")


_CLEAN = [_fy(2024, 43.5e6, 6.4e6, 2.7e6, 26e6, 11e6, 13.5e6, .9e6, 24e6, 2.1e6, .52e6, 1.6e6),
          _fy(2025, 47.8e6, 7.1e6, 3.05e6, 28.5e6, 9.5e6, 14.2e6, .7e6, 26.3e6, 2.8e6, .48e6, 1.6e6)]

# folder -> (extraction fields, requested amount in MAD)
SAMPLES = {
    "01_complete_low_risk": (dict(
        company_name="Fes Ceramique Fictive SARL", legal_form="SARL", ice="008888888000088", rc="RC Fes 88001",
        city="Fes", incorporation_date="2012-05-21", activity="Fabrication de carreaux céramiques",
        sector="manufacturing",
        directors=[dict(name="Youssef Fictif Alami", role="Gérant", nationality="MA")],
        shareholders=[dict(name="Youssef Fictif Alami", type="person", country="MA", pct=65, ubos=[]),
                      dict(name="Leila Fictive Berrada", type="person", country="MA", pct=35, ubos=[])],
        financials=_CLEAN, warnings=[],
        documents=[_doc(0, "statuts"), _doc(1, "modele_J", issued=ISSUED), _doc(2, "attestation_fiscale"),
                   _doc(3, "bilan", 2024), _doc(4, "bilan", 2025), _doc(5, "id_document", holder="Youssef Fictif Alami"),
                   _doc(6, "rapport_solvabilite", holder="Fes Ceramique Fictive SARL"),
                   _doc(7, "rapport_solvabilite", holder="Youssef Fictif Alami"),
                   _doc(8, "rapport_solvabilite", holder="Leila Fictive Berrada")]), 8_000_000),
    "02_incomplete": (dict(
        company_name="Meknes Emballage Fictif SARL", legal_form="SARL", ice="007777777000077",
        rc="RC Meknes 77001", city="Meknes", incorporation_date="2012-05-21", activity="Emballages carton",
        sector="manufacturing",
        directors=[dict(name="Hamza Fictif Chraibi", role="Gérant", nationality="MA")],
        shareholders=[dict(name="Hamza Fictif Chraibi", type="person", country="MA", pct=65, ubos=[]),
                      dict(name="Nora Fictive Lahlou", type="person", country="MA", pct=35, ubos=[])],
        financials=_CLEAN[1:], warnings=[],
        documents=[_doc(0, "statuts"), _doc(1, "modele_J", issued=ISSUED), _doc(2, "bilan", 2025)]), 8_000_000),
    "03_high_risk": (dict(
        company_name="Atlas Negoce International Fictif SARL", legal_form="SARL", ice="006666666000066",
        rc="RC Casablanca 66001", city="Casablanca", incorporation_date="2023-05-10",
        activity="Négoce général import-export", sector="general_trading",
        directors=[dict(name="Samira Bennis Alaoui", role="Gérante", nationality="MA")],
        shareholders=[dict(name="Samira Bennis Alaoui", type="person", country="MA", pct=30, ubos=[]),
                      dict(name="Coral Bay Holdings Ltd", type="company", country="VG", pct=70,
                           ubos=[dict(name="Karim Fictif Tazi", country="MA", pct_of_entity=100)])],
        financials=[_fy(2024, 9.8e6, .9e6, .38e6, 2.1e6, 3.5e6, 6.9e6, 1.2e6, 8.6e6, .4e6, .21e6, .45e6),
                    _fy(2025, 14.2e6, 1.15e6, .42e6, 2.5e6, 4.2e6, 9.8e6, 1.7e6, 11.9e6, .3e6, .26e6, .5e6)],
        warnings=[],
        documents=[_doc(0, "statuts"), _doc(1, "modele_J", issued=ISSUED), _doc(2, "attestation_fiscale"),
                   _doc(3, "bilan", 2024), _doc(4, "bilan", 2025), _doc(5, "id_document", holder="Samira Bennis Alaoui"),
                   _doc(6, "declaration_ubo"), _doc(7, "registre_actionnaires", holder="Coral Bay Holdings Ltd"),
                   _doc(8, "rapport_solvabilite", holder="Atlas Negoce International Fictif SARL"),
                   _doc(9, "rapport_solvabilite", holder="Samira Bennis Alaoui")]), 12_000_000),
}

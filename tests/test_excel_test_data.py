# tests/test_excel_test_data.py
from app.core.excel.test_data import generate_test_roster
from app.core.excel.reader import ExcelReader

MAPPING = {
    'klasse': 'A', 'nachname': 'B', 'vorname': 'C', 'schuelerId': 'D',
    'fotografiert': 'E', 'aufnahmedatum': 'F', 'grund': 'G',
}


def test_generate_test_roster_is_loadable(tmp_path):
    path = tmp_path / 'Testroster.xlsx'
    generate_test_roster(
        path, MAPPING, locations=2, classes_per_location=3, seed=1
    )
    assert path.exists()

    reader = ExcelReader(path, MAPPING)
    locations = reader.locations()
    assert locations == ['Testort 1', 'Testort 2']

    all_ids = []
    total_learners = 0
    for loc in locations:
        classes = reader.classes_for_location(loc)
        assert len(classes) == 3
        for cls in classes:
            learners = reader.learners(loc, cls)
            assert learners, f'no learners for {loc}/{cls}'
            total_learners += len(learners)
            for lr in learners:
                assert lr.nachname
                assert lr.vorname
                assert lr.schueler_id
                assert not lr.photographed
                all_ids.append(lr.schueler_id)

    assert total_learners > 0
    assert len(all_ids) == len(set(all_ids)), 'schueler_ids must be unique'


def test_generate_test_roster_reroll_differs(tmp_path):
    p1 = tmp_path / 'a.xlsx'
    p2 = tmp_path / 'b.xlsx'
    generate_test_roster(p1, MAPPING, seed=1)
    generate_test_roster(p2, MAPPING, seed=2)

    def names(path):
        r = ExcelReader(path, MAPPING)
        out = []
        for loc in r.locations():
            for cls in r.classes_for_location(loc):
                out.extend((lr.nachname, lr.vorname) for lr in r.learners(loc, cls))
        return out

    assert names(p1) != names(p2)

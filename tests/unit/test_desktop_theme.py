from change_plate_next.interfaces.desktop.theme import load_qss


def test_workshop_light_qss_loads() -> None:
    qss = load_qss("workshop_light")
    assert "QPushButton#PrimaryButton" in qss
    assert "#0067C0" in qss
    assert "QFrame#HeroCard" in qss
    assert "QFrame#NavigationView" in qss

from change_plate_next.domain.models import PlateChangeRecipe
from change_plate_next.domain.policies import InsertionStrategy


def test_scaffold_imports() -> None:
    recipe = PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n")
    assert recipe.hotbed_temp == 40
    assert InsertionStrategy.BEFORE_FINISH_SOUND_BLOCK.value == "before_finish_sound_block"

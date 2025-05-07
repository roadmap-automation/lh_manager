from ..liquid_handler.bedlayout import Solution, Composition

WATER = Composition(solvents=[dict(name='H2O',
                                   fraction=1.0)])

class WasteItem(Solution):
    ...
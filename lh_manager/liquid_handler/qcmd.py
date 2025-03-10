from typing import List, Literal

from .lhmethods import InjectMethod, BaseLHMethod
from .methods import register
from .bedlayout import LHBedLayout
from .layoutmap import LayoutWell2ZoneWell, Zone

@register
class QCMD_Record_Sync(BaseLHMethod):
    """Records QCMD Data"""

    Tag_Name: str = ''
    Record_Time: float = 1.5
    Equilibration_Time: float = 2.5
    display_name: Literal['QCMD Record'] = 'QCMD Record'
    method_name: Literal['NCNR_QCMD_Record_Sync'] = 'NCNR_QCMD_Record_Sync'

    class lh_method(BaseLHMethod.lh_method):
        Tag_Name: str
        Record_Time: str
        Equilibration_Time: str

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Tag_Name=self.Tag_Name,
            Record_Time=f'{self.Record_Time}',
            Equilibration_Time=f'{self.Equilibration_Time}'
        )]

@register
class QCMD_Setup(BaseLHMethod):
    """NCNR_QCMD_Setup
    
    NOTE: This probably doesn't work because it sets global variables. Might need an intermediary method
            that sets the global variables"""

    QCMD_Address: str = 'localhost'
    QCMD_Port: int = 5011
    GSIOC_Address: int = 62
    display_name: Literal['QCMD Setup'] = 'QCMD Setup'
    method_name: Literal['NCNR_QCMD_Setup'] = 'NCNR_QCMD_Setup'

    class lh_method(BaseLHMethod.lh_method):
        QCMD_ADDRESS: str
        QCMD_PORT: int
        GSIOC_ADDRESS: int

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            QCMD_ADDRESS=f'{self.QCMD_Address}',
            QCMD_PORT=f'{self.QCMD_Port}',
            GSIOC_ADDRESS=f'{self.GSIOC_Address}'
        )]

#@register
class QCMD_Stop(BaseLHMethod):
    """Stops QCMD recording"""

    display_name: Literal['QCMD Stop'] = 'QCMD Stop'
    method_name: Literal['NCNR_QCMD_Stop'] = 'NCNR_QCMD_Stop'

    class lh_method(BaseLHMethod.lh_method):
        pass

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
        )]

@register
class InjectWithRinseSync(InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.5
    Flow_Rate: float = 2.5
    Outside_Rinse_Volume: float = 0.5
    Extra_Volume: float = 0.1
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    Tag_Name: str = ''
    Record_Time: float = 1.5
    Equilibration_Time: float = 2.5
    display_name: Literal['Inject With Synchronization'] = 'Inject With Synchronization'
    method_name: Literal['NCNR_InjectWithRinse_Sync'] = 'NCNR_InjectWithRinse_Sync'

    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str
        Outside_Rinse_Volume: str
        Extra_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str
        Tag_Name: str
        Record_Time: str
        Equilibration_Time: str

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        comp = repr(well.composition)
        if len(self.Tag_Name):
            comp = ' ' + comp
            
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Extra_Volume=f'{self.Extra_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
            Tag_Name=self.Tag_Name + comp,
            Record_Time=f'{self.Record_Time}',
            Equilibration_Time=f'{self.Equilibration_Time}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

@register
class InjectDoubleSync(InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.5
    Flow_Rate: float = 2.5
    Second_Flow_Rate: float = 2.5
    Second_Volume: float = 1.0
    Outside_Rinse_Volume: float = 0.5
    Extra_Volume: float = 0.1
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    Tag_Name: str = ''
    Record_Time: float = 1.5
    Equilibration_Time: float = 2.5
    display_name: Literal['Inject Double with Synchronization'] = 'Inject Double with Synchronization'
    method_name: Literal['NCNR_InjectDouble_Sync'] = 'NCNR_InjectDouble_Sync'

    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str
        Second_Flow_Rate: str
        Second_Volume: str
        Outside_Rinse_Volume: str
        Extra_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str
        Tag_Name: str
        Record_Time: str
        Equilibration_Time: str

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        comp = repr(well.composition)
        if len(self.Tag_Name):
            comp = ' ' + comp

        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}',
            Second_Flow_Rate=f'{self.Second_Flow_Rate}',
            Second_Volume=f'{self.Second_Volume}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Extra_Volume=f'{self.Extra_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
            Tag_Name=self.Tag_Name + comp,
            Record_Time=f'{self.Record_Time}',
            Equilibration_Time=f'{self.Equilibration_Time}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return (self.Volume + self.Second_Volume) / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate + self.Second_Volume / self.Second_Flow_Rate

@register
class Sync_WaitUntilIdle(BaseLHMethod):
    """Waits until idle signal is received"""

    display_name: Literal['Wait Until Idle'] = 'Wait Until Idle'
    method_name: Literal['NCNR_Sync_WaitUntilIdle'] = 'NCNR_Sync_WaitUntilIdle'

    class lh_method(BaseLHMethod.lh_method):
        pass

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
        )]
    
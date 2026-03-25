"""
New York NEC Jurisdiction Engine
=================================
New York solar jurisdiction engine.

Electrical code: NEC 690 + NYC Building Code (NYC boroughs) /
                 NY State Building Code (rest of NY)
Wire: THWN-2 (same as California / Florida — NEC standard)
Snow load: 30 PSF for NYC metro area; 40 PSF for upstate (Buffalo, Rochester,
           Syracuse, Albany)
Wind: 120 mph design wind for coastal Long Island; 110 mph for rest of NY
Utilities: Con Edison (NYC + Westchester), PSEG Long Island (Nassau/Suffolk),
           National Grid / National Fuel (Buffalo/WNY), RG&E (Rochester),
           National Grid (Syracuse, Albany)
AHJ: "NYC DOB" for the five NYC boroughs; "City of [Name]" otherwise
"""

from typing import Dict, List

from jurisdiction.nec_base import NECBaseEngine


# ---------------------------------------------------------------------------
# City data table
# ---------------------------------------------------------------------------

# Keys are lowercase city names (or borough names).
# 'region': 'nyc' | 'long_island' | 'westchester' | 'upstate'
NY_CITIES = {
    # NYC boroughs
    'new york city':    {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    'manhattan':        {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    'brooklyn':         {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    'queens':           {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    'bronx':            {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    'staten island':    {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'nyc', 'ahj': 'NYC DOB'},
    # Westchester
    'white plains':     {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'westchester', 'ahj': 'City of White Plains'},
    'yonkers':          {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'westchester', 'ahj': 'City of Yonkers'},
    'new rochelle':     {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'westchester', 'ahj': 'City of New Rochelle'},
    # Long Island — Nassau County
    'hempstead':        {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Town of Hempstead'},
    'nassau':           {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Nassau County'},
    'garden city':      {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Village of Garden City'},
    'long beach':       {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'City of Long Beach'},
    # Long Island — Suffolk County
    'suffolk':          {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Suffolk County'},
    'babylon':          {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Town of Babylon'},
    'islip':            {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Town of Islip'},
    'huntington':       {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Town of Huntington'},
    'brentwood':        {'utility': 'PSEG Long Island', 'wind_mph': 120, 'snow_psf': 30, 'region': 'long_island', 'ahj': 'Town of Islip'},
    # Upstate — Western NY
    'buffalo':          {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Buffalo'},
    'niagara falls':    {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Niagara Falls'},
    'tonawanda':        {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Tonawanda'},
    # Upstate — Rochester
    'rochester':        {'utility': 'Rochester Gas & Electric (RG&E)', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Rochester'},
    # Upstate — Syracuse / Central NY
    'syracuse':         {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Syracuse'},
    'utica':            {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Utica'},
    # Upstate — Capital Region
    'albany':           {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Albany'},
    'schenectady':      {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Schenectady'},
    'troy':             {'utility': 'National Grid', 'wind_mph': 110, 'snow_psf': 40, 'region': 'upstate', 'ahj': 'City of Troy'},
    # Default
    '_default':         {'utility': 'Con Edison', 'wind_mph': 110, 'snow_psf': 30, 'region': 'metro', 'ahj': ''},
}

# NYC borough names for AHJ detection
NYC_BOROUGHS = {'new york city', 'manhattan', 'brooklyn', 'queens', 'bronx', 'staten island'}

# Long Island county keywords
LONG_ISLAND_KEYWORDS = {'nassau', 'suffolk', 'long island', 'hempstead', 'babylon',
                        'islip', 'huntington', 'brentwood', 'garden city', 'long beach'}

# Upstate city keywords
UPSTATE_KEYWORDS = {'buffalo', 'rochester', 'syracuse', 'albany', 'utica',
                    'schenectady', 'troy', 'niagara', 'tonawanda'}

# Interconnection standards by utility
UTILITY_INTERCONNECTION = {
    'Con Edison':                     'Con Edison Net Metering / IEEE 1547 (NYSERDA)',
    'PSEG Long Island':               'PSEG Long Island Distributed Generation Interconnection / IEEE 1547',
    'National Grid':                  'National Grid Distributed Generation Interconnection / IEEE 1547',
    'Rochester Gas & Electric (RG&E)': 'RG&E Net Metering / IEEE 1547 (NYSERDA)',
    '_default':                       'NY PSC Net Metering / IEEE 1547',
}


class NYJurisdiction(NECBaseEngine):
    """New York NEC 690 jurisdiction engine.

    Covers NYC boroughs, Long Island (Nassau/Suffolk), Westchester, and
    upstate cities. Handles automatic utility assignment, snow/wind loads,
    and AHJ labelling.
    """

    def __init__(self, city: str = "", state: str = "NY"):
        self.city = city.lower().strip()
        self._state = state
        city_data = self._resolve_city_data()
        self.wind_speed_mph = city_data['wind_mph']
        self.snow_load_psf = city_data['snow_psf']
        self.utility_name = city_data['utility']
        self._region = city_data['region']
        self._ahj = city_data['ahj']
        intercon_key = self.utility_name if self.utility_name in UTILITY_INTERCONNECTION else '_default'
        self._interconnection_std = UTILITY_INTERCONNECTION[intercon_key]
        self._utility_info = {
            'name': self.utility_name,
            'full_name': self.utility_name,
            'interconnection_standard': self._interconnection_std,
            'net_metering_max_kw': 2000,
            'rate_per_kwh': 0.20,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_city_data(self) -> Dict:
        """Match city name against NY_CITIES table using substring matching."""
        city_key = self.city
        for name, data in NY_CITIES.items():
            if name == '_default':
                continue
            if name in city_key or city_key in name:
                return data
        return dict(NY_CITIES['_default'])

    # ------------------------------------------------------------------
    # JurisdictionEngine interface
    # ------------------------------------------------------------------

    def get_code_name(self) -> str:
        if self._region == 'nyc':
            return "NEC 690 + NYC Building Code"
        return "NEC 690 + NY State Building Code"

    def get_code_edition(self) -> str:
        if self._region == 'nyc':
            return "NEC 2020 (NFPA 70-2020) + NYC Building Code 2022"
        return "NEC 2020 (NFPA 70-2020) + NY State Building Code 2020"

    @property
    def wire_type(self) -> str:
        return "THWN-2"

    def get_governing_codes(self) -> List[Dict]:
        codes = [
            {"code": "NEC 2020",   "title": "National Electrical Code",                     "edition": "2020"},
            {"code": "ASCE 7-22",  "title": "Minimum Design Loads for Buildings",            "edition": "2022"},
            {"code": "IFC 2021",   "title": "International Fire Code",                       "edition": "2021"},
            {"code": "UL 1741",    "title": "Inverters, Converters, Controllers",            "edition": "SA"},
            {"code": "UL 2703",    "title": "Mounting Systems, Bonding",                    "edition": "2023"},
            {"code": "IEEE 1547",  "title": "Interconnection Standard",                      "edition": "2018"},
        ]
        if self._region == 'nyc':
            codes.insert(1, {"code": "NYC BC 2022", "title": "New York City Building Code", "edition": "2022"})
        else:
            codes.insert(1, {"code": "NYSBC 2020",  "title": "New York State Building Code", "edition": "2020"})
        return codes

    def get_design_temperatures(self, city: str = "") -> Dict:
        city_key = (city or self.city).lower()
        temps = {
            'new york':   {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
            'manhattan':  {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
            'brooklyn':   {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
            'queens':     {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
            'bronx':      {"cold_c": -15, "hot_module_c": 65, "stc_c": 25},
            'buffalo':    {"cold_c": -20, "hot_module_c": 62, "stc_c": 25},
            'rochester':  {"cold_c": -18, "hot_module_c": 62, "stc_c": 25},
            'syracuse':   {"cold_c": -18, "hot_module_c": 62, "stc_c": 25},
            'albany':     {"cold_c": -18, "hot_module_c": 62, "stc_c": 25},
            'long island': {"cold_c": -12, "hot_module_c": 63, "stc_c": 25},
        }
        for key, t in temps.items():
            if key in city_key:
                return t
        return {"cold_c": -15, "hot_module_c": 65, "stc_c": 25}  # NYC metro default

    def get_fire_setbacks(self, building_type: str = "residential") -> Dict:
        """NEC 690.12 rapid shutdown + IFC setbacks (NY Building Code).

        NYC Building Code / NYSBC: 18" ridge, 36" sides/eave for residential.
        """
        if building_type == "residential":
            return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 3.0}
        return {"ridge_ft": 1.5, "eave_ft": 3.0, "pathway_ft": 4.0}

    def get_wind_snow_loads(self, city: str = "") -> Dict:
        """NY wind and snow loads per ASCE 7-22.

        Snow: 30 PSF NYC metro / Westchester / Long Island; 40 PSF upstate.
        Wind: 120 mph coastal Long Island; 110 mph rest of NY.
        """
        return {"wind_mph": self.wind_speed_mph, "snow_psf": self.snow_load_psf}

    def get_utility_info(self, city: str = "") -> Dict:
        if city and city.lower().strip() != self.city:
            return NYJurisdiction(city=city)._utility_info
        return self._utility_info

    def get_ahj_label(self, city: str = "") -> str:
        """Return AHJ label. NYC boroughs use NYC DOB; all others use City of [Name]."""
        city_key = (city or self.city).lower().strip()
        # Check if it's a NYC borough
        for borough in NYC_BOROUGHS:
            if borough in city_key or city_key in borough:
                return "NYC DOB"
        # Check stored AHJ
        if self._ahj:
            return self._ahj
        # Fallback
        city_title = (city or self.city).strip().title()
        if city_title:
            return f"City of {city_title}"
        return "Local Building Department (New York)"

    def get_contractor_license_type(self) -> str:
        return "NYS Licensed Electrical Contractor (LEC)"

    def get_licensing_body(self) -> str:
        return "NYSDOS"

    def get_licensing_body_full(self) -> str:
        return "New York State Department of State (NYSDOS)"

    def get_general_notes(self) -> List[str]:
        return [
            "1. This drawing sets minimum standards for construction. All work shall comply with NEC 2020 (NFPA 70-2020) and all applicable local ordinances.",
            f"2. Governing building code: {self.get_code_name()}.",
            "3. All equipment shall be installed per manufacturer's installation manuals. Notify the contractor of any discrepancies prior to beginning work.",
            "4. Prior to the commencement of any work, the contractor shall visit the site to fully verify all existing conditions.",
            "5. All effort must be made by the general contractor and subcontractors to mount equipment level and secure.",
            "6. Beams or joists shall not be drilled unless specifically authorized by the structural engineer of record.",
            f"7. A permit must be obtained from the Authority Having Jurisdiction ({self.get_ahj_label()}) prior to commencing any work.",
            "8. The local utility shall be notified prior to interconnection.",
            f"9. Interconnection per {self._interconnection_std}.",
            "10. Rapid shutdown equipment shall comply with NEC 2020 Section 690.12.",
            "11. All conductors shall be THWN-2 rated for wet locations.",
            f"12. Wind design per ASCE 7-22: {self.wind_speed_mph} mph design wind speed. Snow load: {self.snow_load_psf} PSF.",
            "13. All drawings and notes are not to scale. Contractor shall check and verify all dimensions at the job site.",
        ]

    def get_electrical_notes(self) -> List[str]:
        return [
            "1. The equipment and all associated wiring shall be installed only by qualified persons holding a valid NYS LEC license. (NEC 2020 690.4(E))",
            "2. The local utility shall be notified prior to activation of any solar photovoltaic installation.",
            "3. All PV conductors shall be THWN-2 rated.",
            "4. DC conductors shall comply with NEC 2020 690.8(A): Isc × 1.25 × 1.25 (Isc × 1.56).",
            "5. AC breaker sizing per NEC 2020 690.8(A): continuous current × 1.25.",
            "6. Interconnection per NEC 2020 705.12 (120% rule or supply-side tap).",
            "7. Rapid shutdown shall comply with NEC 2020 Section 690.12.",
            "8. All inverters shall be UL 1741 SA listed and compliant with NY utility requirements.",
            "9. Equipment grounding conductor per NEC 2020 Table 250.122.",
            "10. Voltage drop shall be limited to 2% for branch circuits and 3% cumulative.",
            "11. All conduit sizes and types specified in single-line and/or three-line diagrams shall be installed.",
            "12. The backfeed breaker shall be at the opposite end of the bus from the main breaker.",
            "13. All PV source circuits shall have individual overcurrent protection per NEC 2020 690.9.",
            f"14. Snow load design: {self.snow_load_psf} PSF per ASCE 7-22. Racking shall be certified for this load.",
        ]

    def get_jurisdiction_data(self, city: str = "", state: str = "NY") -> Dict:
        """Return a flat summary dict.  Accepts optional city/state to re-resolve."""
        if city and city.lower().strip() != self.city:
            return NYJurisdiction(city=city, state=state).get_jurisdiction_data()
        return {
            "utility":         self.utility_name,
            "wire_type":       self.wire_type,
            "electrical_code": self.get_code_edition(),
            "utility_full":    self.utility_name,
            "wind_mph":        self.wind_speed_mph,
            "snow_load_psf":   self.snow_load_psf,
            "snow_psf":        self.snow_load_psf,
            "ahj":             self.get_ahj_label(),
            "licensing_body":  self.get_licensing_body(),
            "code_name":       self.get_code_name(),
        }

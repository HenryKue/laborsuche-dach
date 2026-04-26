from enum import Enum

class ServiceType(str, Enum):
    BODY_COMPOSITION = 'body_composition'
    BONE_DENSITY = 'bone_density'
    SELF_PAY_BLOOD_TEST = 'blood_test'

class Country(str, Enum):
    DE = 'DE'
    AT = 'AT'
    CH = 'CH'
import ee

def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Applies cloud and shadow mask using Sentinel-2 L2A Scene Classification Layer (SCL).
    Excludes SCL classes: 3 (cloud shadow), 8 (cloud medium prob), 9 (cloud high prob), 10 (thin cirrus).
    """
    scl = image.select("SCL")
    valid_mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return image.updateMask(valid_mask)

def calculate_water_indices(image: ee.Image) -> ee.Image:
    """Calculates NDWI (B3, B8) and MNDWI (B3, B11)."""
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    mndwi = image.normalizedDifference(["B3", "B11"]).rename("MNDWI")
    return image.addBands([ndwi, mndwi])

def compute_rgb(image: ee.Image) -> ee.Image:
    """Generates 8-bit True Color RGB (B4, B3, B2)."""
    rgb = image.select(["B4", "B3", "B2"]).divide(10000).clamp(0, 0.3).divide(0.3).multiply(255).uint8()
    return rgb.rename(["R", "G", "B"])

def detect_water_change(before_mndwi: ee.Image, during_mndwi: ee.Image, 
                         mndwi_threshold: float = 0.1, min_increase: float = 0.2) -> ee.Image:
    """Detects newly appeared water pixels using MNDWI thresholding."""
    diff = during_mndwi.subtract(before_mndwi)
    is_water = during_mndwi.gt(mndwi_threshold)
    increased = diff.gt(min_increase)
    return is_water.And(increased).rename("flooded")
from typing import List, Tuple, Union

class Link:
    def __init__(self, uri: str, bounds: Tuple[float, float, float, float], page_width: float, page_height: float):
        self.uri = uri
        self.bounds = bounds  # (x0, y0, x1, y1)
        self.bounds_width = bounds[2] - bounds[0]
        self.bounds_height = bounds[3] - bounds[1]
        # Normalize bounds
        self.normalized_bounds = (
            bounds[0] / page_width,
            bounds[1] / page_height,
            bounds[2] / page_width,
            bounds[3] / page_height
        )

    def __repr__(self):
        return f"Link(uri={self.uri}, bounds={self.bounds}, normalized_bounds={self.normalized_bounds}, bounds_width={self.bounds_width}, bounds_height={self.bounds_height})"

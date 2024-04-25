


class CoordinateConverter:

    def resonite_to_selenium(self,
                             resonite_x: int,
                             resonite_y: int,
                             resonite_canvas_size_x: int,
                             resonite_canvas_size_y: int,
                             resonite_normalized_position_y: float,
                             webpage_size_x: int,
                             webpage_size_y: int) -> (float, float):

        if resonite_x < 0:
            selenium_x = (resonite_canvas_size_x / 2) - abs(resonite_x)
        else:
            selenium_x = (resonite_canvas_size_x / 2) + resonite_x

        if resonite_y < 0:
            selenium_y = (resonite_canvas_size_y / 2) + abs(resonite_y)
        else:
            selenium_y = (resonite_canvas_size_y / 2) - resonite_y

        if resonite_normalized_position_y > 0:
            offset_y = (webpage_size_y - resonite_canvas_size_y) * resonite_normalized_position_y
            selenium_y += offset_y

        return selenium_x, selenium_y



if __name__ == '__main__':
    cc = CoordinateConverter()
    resonite_x = 929
    resonite_y = -528

    resonite_canvas_size_x = 1920
    resonite_canvas_size_y = 1080
    resonite_normalized_position_y = 1
    webpage_size_x = 1920
    webpage_size_y = 3364
    selenium_x, selenium_y = cc.resonite_to_selenium(resonite_x, resonite_y, resonite_canvas_size_x, resonite_canvas_size_y, resonite_normalized_position_y, webpage_size_x, webpage_size_y)
    print(f"resonite_x: {resonite_x}, resonite_y: {resonite_y} converted to selenium_x: {selenium_x}, selenium_y: {selenium_y}")

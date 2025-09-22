x, y = 93.1, 109.3

# offsets (change these to whatever you want)
dx, dy = 0,-5

# how many coords to generate
steps = 20

coords = []
for i in range(1, steps + 1):
    new_x = x + i * dx
    new_y = y + i * dy
    coords.append((round(new_x, 2), round(new_y, 2)))

# print results
for c in coords:
    print(f"{c[0]},{c[1]}")
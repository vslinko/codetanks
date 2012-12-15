import math
import tkinter
import os
import functools
from model.BonusType import BonusType
from model.FireType import FireType
from model.TankType import TankType


ATTACK_ANGLE = math.pi / 180 # 1 degree
COMING_SHELL_ANGLE = math.pi / 6 # 30 degrees
PERPENDICULAR_ANGLE = math.pi / 2 # 90 degrees
PERPENDICULAR_ANGLE_MARGIN = math.pi / 9 # 20 degrees
OBSTACLE_ANGLE = math.pi / 18 # 10 degrees
MOVE_ANGLE = math.pi / 9 # 20 degrees
CREW_HEALTH_PANIC = .75
HULL_DURABILITY_PANIC = .5


class FakeDebug(object):
    def point(self, x, y, fill):
        pass

    def polygon(self, coordinates, fill="black"):
        pass

    def render(self):
        pass


class Debug(FakeDebug):
    SCALE = .35
    POINT_RADIUS = 20

    def __init__(self):
        width = 1280 * self.SCALE
        height = 800 * self.SCALE

        self.root = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.root, width=width, height=height)
        self.canvas.pack()
        self.root.update()
        self.root.geometry('%dx%d+%d+%d' % (width, height, self.root.winfo_screenwidth() - width, 0))

    def point(self, x, y, fill):
        x1 = (x - self.POINT_RADIUS) * self.SCALE
        y1 = (y - self.POINT_RADIUS) * self.SCALE
        x2 = (x + self.POINT_RADIUS) * self.SCALE
        y2 = (y + self.POINT_RADIUS) * self.SCALE
        self.canvas.create_oval((x1, y1, x2, y2), fill=fill, tags="object")

    def polygon(self, coordinates, fill="black"):
        coordinates = [(c[0] * self.SCALE, c[1] * self.SCALE) for c in coordinates]
        self.canvas.create_polygon(coordinates, fill=fill, tags="object")

    def render(self):
        self.root.update()
        self.canvas.delete("object")

debug_screen = Debug() if os.getenv("CODETANKS_DEBUG_SCREEN") else FakeDebug()


def enemy(tank):
    """
    :type tank: model.Tank.Tank
    """
    return not tank.teammate and tank.crew_health > 0 and tank.hull_durability > 0


def probably_attacking(tank, unit):
    """
    :type tank: model.Tank.Tank
    :type unit: model.Unit.Unit
    """
    return -ATTACK_ANGLE < tank.get_turret_angle_to_unit(unit) < ATTACK_ANGLE


def coming_shell(me, shell):
    """
    :type me: model.Tank.Tank
    :type shell: model.Shell.Shell
    """
    return -COMING_SHELL_ANGLE < shell.get_angle_to_unit(me) < COMING_SHELL_ANGLE


def possible_obstacle(tank):
    """
    :type tank: model.Tank.Tank
    """
    return tank.teammate or tank.crew_health == 0 or tank.hull_durability == 0


def closing_to_my_way(me, unit):
    """
    :type me: model.Tank.Tank
    :type unit: model.Unit.Unit
    """
    if abs(me.get_angle_to_unit(unit)) < PERPENDICULAR_ANGLE_MARGIN:
        return True

    if abs(math.pi - me.get_angle_to_unit(unit)) < PERPENDICULAR_ANGLE_MARGIN:
        return True

    if me.get_distance_to_unit(unit) < me.height * 5:
        return True

    return False


def lines_intersection(line1, line2):
    """
    :param line1: First line, for example ((1, 1), (2, 2))
    :type line1: tuple
    :param line2: Second line, for example ((1, 2), (2, 1))
    :type line2: tuple
    """

    def intersection(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
        """
        :type ax1: float
        :type ay1: float
        :type ax2: float
        :type ay2: float
        :type bx1: float
        :type by1: float
        :type bx2: float
        :type by2: float
        """
        v1 = (bx2 - bx1) * (ay1 - by1) - (by2 - by1) * (ax1 - bx1)
        v2 = (bx2 - bx1) * (ay2 - by1) - (by2 - by1) * (ax2 - bx1)
        v3 = (ax2 - ax1) * (by1 - ay1) - (ay2 - ay1) * (bx1 - ax1)
        v4 = (ax2 - ax1) * (by2 - ay1) - (ay2 - ay1) * (bx2 - ax1)

        return v1 * v2 < 0 and v3 * v4 < 0

    return intersection(line1[0][0], line1[0][1], line1[1][0], line1[1][1],
        line2[0][0], line2[0][1], line2[1][0], line2[1][1])


def has_obstacles(line, possible_obstacles):
    return False


def nearest(me, units):
    """
    :type me: model.Tank.Tank
    :type bonuses: list of model.Unit.Unit
    """
    if not units:
        return None

    return min(units, key=lambda u: me.get_distance_to_unit(u))


def get_by_id(units, id):
    """
    :type units: list of model.Unit.Unit
    :param id: int
    """
    filtered_units = [u for u in units if u.id == id]

    return filtered_units[0] if len(filtered_units) == 1 else None


def attack(me, unit, possible_obstacles, move):
    """
    :type me: model.Tank.Tank
    :type unit: model.Unit.Unit
    :type possible_obstacles: list of model.Unit.Unit
    :type move: model.Move.Move
    """
    distance = me.get_distance_to_unit(unit)
    shell_speed = 13 if me.premium_shell_count > 0 else 15
    enemy_speed = math.sqrt(math.pow(unit.speedX, 2) + math.pow(unit.speedY, 2))
    enemy_path = enemy_speed * distance / shell_speed
    Cx = unit.x + enemy_path * math.cos(unit.angle)
    Cy = unit.y + enemy_path * math.sin(unit.angle)

    debug_screen.point(me.x, me.y, "red")
    debug_screen.point(unit.x, unit.y, "blue")
    debug_screen.polygon([(me.x, me.y), (unit.x, unit.y), (Cx, Cy)])

    angle = me.get_turret_angle_to(Cx, Cy)

    if angle > ATTACK_ANGLE:
        move.turret_turn = 1
    elif angle < -ATTACK_ANGLE:
        move.turret_turn = -1
    elif not has_obstacles(((me.x, me.y), (Cx, Cy)), possible_obstacles):
        move.fire_type = FireType.PREMIUM_PREFERRED


def _move(tracks_power, move):
    """
    :type tracks_power: tuple
    :type move: model.Move.Move
    :type remember: bool
    """
    move.left_track_power = tracks_power[0]
    move.right_track_power = tracks_power[1]

move_forward = functools.partial(_move, (1, 1))
move_backward = functools.partial(_move, (-1, -1))
turn_right = functools.partial(_move, (.75, -1))
turn_left = functools.partial(_move, (-1, .75))


def follow(me, unit, move):
    """
    :type me: model.Tank.Tank
    :type unit: list of model.Unit.Unit
    :type move: model.Move.Move
    """
    angle = me.get_angle_to_unit(unit)
    reverse = False

    if angle > PERPENDICULAR_ANGLE:
        angle -= math.pi
        reverse = True
    elif angle < -PERPENDICULAR_ANGLE:
        angle += math.pi
        reverse = True

    if angle > MOVE_ANGLE:
        turn_right(move)
    elif angle < -MOVE_ANGLE:
        turn_left(move)
    elif reverse:
        move_backward(move)
    else:
        move_forward(move)


def hide_from_shell(me, shell, move):
    """
    :type me: model.Tank.Tank
    :type shell: model.Shell.Shell
    :type move: model.Move.Move
    """
    angle = me.get_angle_to_unit(shell)

    if abs(angle) > PERPENDICULAR_ANGLE:
        move_forward(move)
    else:
        move_backward(move)


def turn_perpendicular(me, units, move):
    """
    :type me: model.Tank.Tank
    :type units: list of model.Unit.Unit
    :type move: model.Move.Move
    """
    angles = [me.get_angle_to_unit(u) for u in units]
    angle = sum(angles) / len(angles)
    reverse = True

    if angle > PERPENDICULAR_ANGLE:
        angle -= math.pi
        reverse = False
    elif angle < -PERPENDICULAR_ANGLE:
        angle += math.pi
        reverse = False

    right = turn_left if reverse else turn_right
    left = turn_right if reverse else turn_left

    if angle > PERPENDICULAR_ANGLE + PERPENDICULAR_ANGLE_MARGIN:
        left(move)
    elif angle < PERPENDICULAR_ANGLE - PERPENDICULAR_ANGLE_MARGIN:
        right(move)
    else:
        return False

    return True


class MyStrategy(object):
    tank_id = None

    def move(self, me, world, move):
        """
        :type me: model.Tank.Tank
        :type world: model.World.World
        :type move: model.Move.Move
        """
        enemies = [t for t in world.tanks if enemy(t)]
        attacking_enemies = [e for e in enemies if probably_attacking(e, me)]
        remembered_enemy = get_by_id(attacking_enemies, self.tank_id)
        possible_obstacles = [t for t in world.tanks if possible_obstacle(t)] + world.obstacles + world.bonuses
        coming_shells = [s for s in world.shells if coming_shell(me, s)]
        nearest_coming_shell = nearest(me, coming_shells)
        med_kits = [b for b in world.bonuses if b.type == BonusType.MEDIKIT]
        nearest_med_kit = nearest(me, med_kits)
        repair_kits = [b for b in world.bonuses if b.type == BonusType.REPAIR_KIT]
        nearest_repair_kit = nearest(me, repair_kits)
        ammo_crates = [b for b in world.bonuses if b.type == BonusType.AMMO_CRATE]
        closing_to_my_way_ammo_crates = [b for b in ammo_crates if closing_to_my_way(me, b)]
        nearest_closing_to_my_way_ammo_crate = nearest(me, closing_to_my_way_ammo_crates)
        closing_to_my_way_bonuses = [b for b in world.bonuses if closing_to_my_way(me, b)]
        nearest_closing_to_my_way_bonus = nearest(me, closing_to_my_way_bonuses)

        if remembered_enemy:
            target = remembered_enemy
        elif attacking_enemies:
            target = min(attacking_enemies, key=lambda e: e.crew_health)
            self.tank_id = target.id
        else:
            target = min(enemies, key=lambda e: me.get_turret_angle_to_unit(e))

        attack(me, target, possible_obstacles, move)

        if me.crew_health < me.crew_max_health * CREW_HEALTH_PANIC and nearest_med_kit:
            follow(me, nearest_med_kit, move)
        elif nearest_coming_shell:
            hide_from_shell(me, nearest_coming_shell, move)
        elif me.hull_durability < me.hull_max_durability * HULL_DURABILITY_PANIC and nearest_repair_kit:
            follow(me, nearest_repair_kit, move)
        elif nearest_closing_to_my_way_ammo_crate:
            follow(me, nearest_closing_to_my_way_ammo_crate, move)
        elif not turn_perpendicular(me, enemies, move) and nearest_closing_to_my_way_bonus:
            follow(me, nearest_closing_to_my_way_bonus, move)
        else:
            pass

        debug_screen.render()

    def select_tank(self, tank_index, team_size):
        """
        :type tank_index: int
        :type team_size: int
        """
        return TankType.MEDIUM

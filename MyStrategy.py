import math
import functools
from model.BonusType import BonusType
from model.FireType import FireType
from model.TankType import TankType


ATTACK_ANGLE = math.pi / 180 # 1 degree
COMING_SHELL_ANGLE = math.pi / 6 # 30 degrees
PERPENDICULAR_ANGLE = math.pi / 2 # 90 degrees
PERPENDICULAR_ANGLE_MARGIN = math.pi / 9 # 20 degrees
MOVE_ANGLE = math.pi / 9 # 20 degrees
CREW_HEALTH_PANIC = .75
HULL_DURABILITY_PANIC = .5


def enemy(tank):
    """
    :type tank: model.Tank.Tank
    """
    return not tank.teammate and tank.crew_health > 0


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


def attack(me, unit, move):
    """
    :type me: model.Tank.Tank
    :type unit: model.Unit.Unit
    :type move: model.Move.Move
    """

    def attack_angle_deviation(distance, enemy_speed, shell_speed, gamma):
        """
        :param distance: Distance between me and enemy
        :type distance: float
        :param enemy_speed: Enemy speed
        :type enemy_speed: float
        :param shell_speed: Shell speed
        :type shell_speed: float
        :param gamma: Angle between enemy path and me
        :type gamma: float
        """
        if gamma == 0 or gamma == math.pi or enemy_speed == 0:
            return 0

        b = distance
        a = enemy_speed * distance / shell_speed
        c = math.sqrt(math.pow(a, 2) + math.pow(b, 2) - 2 * a * b * math.cos(gamma))
        alpha = math.acos(round((math.pow(b, 2) + math.pow(c, 2) - math.pow(a, 2)) / (2 * b * c), 10))

        return -alpha if (gamma < 0) != (enemy_speed < 0) else alpha

    distance = me.get_distance_to_unit(unit)
    enemy_speed = math.sqrt(math.pow(unit.speedX, 2) + math.pow(unit.speedY, 2))
    shell_speed = 13 if me.premium_shell_count > 0 else 15
    gamma = unit.get_angle_to_unit(me)
    angle_deviation = attack_angle_deviation(distance, enemy_speed, shell_speed, gamma)
    angle = me.get_turret_angle_to_unit(unit) + angle_deviation

    if angle > ATTACK_ANGLE:
        move.turret_turn = 1
    elif angle < -ATTACK_ANGLE:
        move.turret_turn = -1
    else:
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

        attack(me, target, move)

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

    def select_tank(self, tank_index, team_size):
        """
        :type tank_index: int
        :type team_size: int
        """
        return TankType.MEDIUM

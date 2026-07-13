# ------------------------------------------------------------
# Horde Attack – a text‑based roguelike (rewritten & improved)
# ------------------------------------------------------------

# ────────────────────── Imports ─────────────────────────────
import json
import os
import random
import sys
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable

# ────────────────────── Constants ────────────────────────
# ---- Game start values -------------------------------------------------
STARTING_HP: int = 25
STARTING_ARMOUR: int = 0
STARTING_DAMAGE: Tuple[int, int] = (1, 5)          # (min, max)
STARTING_CRIT_CHANCE: int = 10                    # percent

# ---- Scaling / balance -------------------------------------------------
CRIT_MULTIPLIER: float = 2.5
WAVE_BONUS_HP: int = 2
UPGRADE_SCORE_STEP: int = 10                      # points needed per level‑up

# ---- Upgrade values ----------------------------------------------------
HP_UPGRADE_VALUE: int = 5
DMG_UPGRADE_VALUE: int = 1
ARMOUR_UPGRADE_VALUE: int = 2
SCORE_BONUS_VALUE: int = 2
CRIT_UPGRADE_VALUE: int = 4                       # percent per upgrade
MAX_CRIT_CHANCE: int = 100

# ---- Miscellaneous ------------------------------------------------------
RECOVER_MIN: int = 8
RECOVER_MAX: int = 12
HEALER_CHANCE: int = 75            # % chance a Healer will heal an ally
SPECIAL_ATTACK_CHANCE: float = 0.25  # 25 % chance to use special attack
BONUS_WAVE_OFFSET: int = 2         # first bonus wave = wave 2

# ---- File handling -------------------------------------------------------
HIGHSCORE_FILE: Path = Path("highscore.json")

# ────────────────────── Helper functions ──────────────────────
def clear_screen() -> None:
    """Cross‑platform screen clear."""
    os.system("cls" if os.name == "nt" else "clear")


def get_key() -> str:
    """
    Return a *complete* key code without requiring Enter.
    Handles both Unix (escape sequences) and Windows (msvcrt) keys.
    """
    try:
        import msvcrt                     # Windows
        first = msvcrt.getch()
        if first in (b"\x00", b"\xe0"):    # special key prefix
            second = msvcrt.getch()
            return {
                b"H": "\x1b[A",  # Up
                b"P": "\x1b[B",  # Down
                b"K": "\x1b[D",  # Left
                b"M": "\x1b[C",  # Right
            }.get(second, second.decode())
        return first.decode()
    except ImportError:                    # Unix / macOS
        if not sys.stdin.isatty():
            # non‑interactive fallback – behave like a normal input()
            return input()
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch += sys.stdin.read(2)   # eat the rest of the escape
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def load_highscore() -> Tuple[int, str, int]:
    """Load high‑score data, creating a default file if needed."""
    if not HIGHSCORE_FILE.exists():
        save_highscore(0, "", 0)
        return 0, "", 0

    try:
        with HIGHSCORE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        return data["highscore"], data["record_holder"], data["kill_count"]
    except (json.JSONDecodeError, KeyError, OSError):
        # Corrupt file – reset to defaults
        save_highscore(0, "", 0)
        return 0, "", 0


def save_highscore(score: int, holder: str, kills: int) -> None:
    """Write high‑score data atomically."""
    tmp = HIGHSCORE_FILE.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(
                {"highscore": score, "record_holder": holder, "kill_count": kills},
                f,
                indent=4,
            )
        tmp.replace(HIGHSCORE_FILE)          # atomic on most platforms
    except OSError as exc:
        print(f"⚠️  Could not write highscore: {exc}")


def navigate_menu(options: List[str], title: str) -> int:
    """
    Render a simple vertical menu and return the index of the chosen option.
    """
    selected = 0
    while True:
        clear_screen()
        print(f"=== {title} ===")
        for i, opt in enumerate(options):
            prefix = "> " if i == selected else "  "
            print(f"{prefix}{opt}")
        print("\nUse 'w'/↑ to move, 's'/↓ to move, Enter to select")
        key = get_key()
        norm = key.lower() if len(key) == 1 else key
        if norm == "w" or key == "\x1b[A":
            selected = (selected - 1) % len(options)
        elif norm == "s" or key == "\x1b[B":
            selected = (selected + 1) % len(options)
        elif norm in ("\r", "\n"):
            return selected
        # ignore everything else


# ────────────────────── Data structures ──────────────────────
@dataclass
class Player:
    """The user‑controlled knight."""
    name: str
    max_hp: int = STARTING_HP
    hp: int = field(init=False)
    armour: int = STARTING_ARMOUR
    min_damage: int = STARTING_DAMAGE[0]
    max_damage: int = STARTING_DAMAGE[1]
    crit_chance: int = STARTING_CRIT_CHANCE
    score: int = 0
    score_bonus: int = 0
    kills: int = 0
    level: int = 0
    upgrades: Dict[str, int] = field(
        default_factory=lambda: {
            "HP Upgrade": 0,
            "Armour Upgrade": 0,
            "Damage Upgrade": 0,
            "Score Upgrade": 0,
            "Crit Upgrade": 0,
        }
    )

    def __post_init__(self) -> None:
        self.hp = self.max_hp

    # ---------- basic stats ----------
    def damage(self) -> int:
        return random.randint(self.min_damage, self.max_damage)

    def is_alive(self) -> bool:
        return self.hp > 0

    def heal(self, amount: int) -> None:
        self.hp = min(self.hp + amount, self.max_hp)

    def take_damage(self, dmg: int) -> int:
        """Apply armour and reduce HP. Returns the actual damage taken."""
        actual = max(0, dmg - self.armour)
        self.hp -= actual
        return actual

    # ---------- combat ----------
    def attack(self, enemy: "Enemy") -> Tuple[int, bool]:
        """Deal damage to *enemy* and return (damage_dealt, was_crit)."""
        base = self.damage()
        crit = random.randint(1, 100) <= self.crit_chance
        dmg = int(base * (CRIT_MULTIPLIER if crit else 1))
        if crit:
            print("CRITICAL HIT!")
        actual = enemy.take_damage(dmg, ignore_armour=crit)
        return actual, crit

    # ---------- upgrades ----------
    def upgrade_hp(self) -> None:
        self.max_hp += HP_UPGRADE_VALUE
        self.hp += HP_UPGRADE_VALUE
        self.upgrades["HP Upgrade"] += 1

    def upgrade_damage(self) -> None:
        # randomly bump min or max
        if random.randint(1, 2) == 1:
            self.min_damage += DMG_UPGRADE_VALUE
        else:
            self.max_damage += DMG_UPGRADE_VALUE
        self.upgrades["Damage Upgrade"] += 1

    def upgrade_armour(self) -> None:
        self.armour += ARMOUR_UPGRADE_VALUE
        self.upgrades["Armour Upgrade"] += 1

    def upgrade_score_bonus(self) -> None:
        self.score_bonus += SCORE_BONUS_VALUE
        self.upgrades["Score Upgrade"] += 1

    def upgrade_crit(self) -> None:
        self.crit_chance = min(MAX_CRIT_CHANCE,
                               self.crit_chance + CRIT_UPGRADE_VALUE)
        self.upgrades["Crit Upgrade"] += 1

    def apply_random_upgrade(self) -> str:
        """Pick a random upgrade, apply it and return its name."""
        choices: List[Tuple[str, Callable[[], None]]] = [
            ("HP Upgrade", self.upgrade_hp),
            ("Damage Upgrade", self.upgrade_damage),
            ("Armour Upgrade", self.upgrade_armour),
            ("Score Upgrade", self.upgrade_score_bonus),
            ("Crit Upgrade", self.upgrade_crit),
        ]
        name, func = random.choice(choices)
        func()
        return name


@dataclass
class Enemy:
    """Base enemy – immutable stats are supplied via subclass __init__."""
    name: str
    hp: int
    armour: int
    min_damage: int
    max_damage: int
    value: int
    max_hp: int = field(init=False)

    def __post_init__(self) -> None:
        self.max_hp = self.hp

    # ---------- basic ----------
    def damage(self) -> int:
        return random.randint(self.min_damage, self.max_damage)

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int, *, ignore_armour: bool = False) -> int:
        """Apply damage, respecting armour unless ``ignore_armour`` is True.
        Returns the amount of HP actually removed."""
        if not ignore_armour:
            dmg = max(0, dmg - self.armour)
        self.hp -= dmg
        return dmg

    # ---------- combat ----------
    def attack(self, player: Player) -> int:
        """Normal attack against the player."""
        dmg = self.damage()
        return player.take_damage(dmg)

    def special_attack(self, player: Player) -> int:
        """Default special attack simply calls normal attack."""
        return self.attack(player)


# ----- concrete enemy types ---------------------------------
class Gremlin(Enemy):
    def __init__(self) -> None:
        super().__init__("Gremlin", hp=1, armour=0, min_damage=1, max_damage=1,
                         value=1)


class Goblin(Enemy):
    def __init__(self) -> None:
        super().__init__("Goblin", hp=5, armour=0, min_damage=1, max_damage=2,
                         value=4)

    def special_attack(self, player: Player) -> int:
        # +1 damage on special
        dmg = self.damage() + 1
        return player.take_damage(dmg)


class Healer(Enemy):
    def __init__(self) -> None:
        super().__init__("Healer", hp=10, armour=0, min_damage=1, max_damage=1,
                         value=5)

    def heal_ally(self, allies: List[Enemy]) -> Tuple[Optional[Enemy], int]:
        """Heal a random wounded ally (excluding self). Returns (target, amount)."""
        candidates = [
            e for e in allies
            if e.is_alive() and e is not self and e.hp < e.max_hp
        ]
        if not candidates:
            return None, 0
        target = random.choice(candidates)
        # Healing scales a little with wave later – keep simple for now
        heal_amount = 5
        target.hp = min(target.hp + heal_amount, target.max_hp)
        return target, heal_amount


class Ogre(Enemy):
    def __init__(self) -> None:
        super().__init__("Ogre", hp=15, armour=0, min_damage=1, max_damage=2,
                         value=10)

    def special_attack(self, player: Player) -> int:
        dmg = self.damage() * 2
        return player.take_damage(dmg)


class Dragon(Enemy):
    def __init__(self) -> None:
        super().__init__("Dragon", hp=25, armour=2, min_damage=3, max_damage=8,
                         value=25)

    def special_attack(self, player: Player) -> int:
        dmg = self.damage()
        reduced_armour = player.armour // 2
        dmg = max(0, dmg - reduced_armour)
        player.hp -= dmg       # bypass armour check – dragon flame
        return dmg


# ────────────────────── Game core ──────────────────────
class Game:
    def __init__(self) -> None:
        self.player: Optional[Player] = None
        self.enemies: List[Enemy] = []
        self.next_upgrade_score: int = 5
        self.wave_number: int = 1
        self.game_over: bool = False

    # ---------- menus ----------
    def start_menu(self) -> str:
        choice = navigate_menu(
            ["Start New Game", "View Highscores", "Quit"], "HORDE ATTACK"
        )
        return ["start", "highscores", "quit"][choice]

    def game_menu(self) -> str:
        choice = navigate_menu(
            ["Resume Game", "View Stats", "Quit Game"], "GAME MENU"
        )
        return ["resume", "stats", "quit"][choice]

    # ---------- high‑score ----------
    def show_highscores(self) -> None:
        clear_screen()
        print("=== HIGHSCORES ===")
        print(f"Record: {highscore} points (held by {record_holder})")
        if self.player:
            print(f"Your current score: {self.player.score}")

    # ---------- player ----------
    def init_player(self, name: str) -> None:
        self.player = Player(name)

    # ---------- enemy spawning ----------
    def _scale_enemy(self, enemy: Enemy) -> Enemy:
        """Apply wave‑based scaling to hp and damage."""
        hp_mult = 1 + (self.wave_number * 0.08)
        dmg_mult = 1 + (self.wave_number * 0.05)

        enemy.hp = int(enemy.hp * hp_mult)
        enemy.max_hp = enemy.hp
        enemy.min_damage = int(enemy.min_damage * dmg_mult)
        enemy.max_damage = int(enemy.max_damage * dmg_mult)
        return enemy

    def spawn_enemy(self) -> Enemy:
        """Create a single enemy respecting current wave difficulty."""
        roll = random.randint(1, 100)

        # Choose base enemy type
        if self.wave_number < 4:                      # early game
            enemy = Gremlin() if roll <= 60 else Goblin()
        elif self.wave_number < 7:                    # mid game
            if roll <= 30:
                enemy = Gremlin()
            elif roll <= 80:
                enemy = Goblin()
            else:
                enemy = Ogre()
        elif self.wave_number < 10:                   # late game
            if roll <= 20:
                enemy = Gremlin()
            elif roll <= 60:
                enemy = Goblin()
            elif roll <= 90:
                enemy = Ogre()
            else:
                enemy = Dragon()
        else:                                         # wave 10+
            if roll <= 10:
                enemy = Gremlin()
            elif roll <= 40:
                enemy = Goblin()
            elif roll <= 70:
                enemy = Ogre()
            else:
                enemy = Dragon()

        return self._scale_enemy(enemy)

    def spawn_wave(self) -> None:
        print(f"\n--- Wave {self.wave_number} ---")
        # Bonus wave logic (every 3rd wave: 2, 5, 8, …)
        if (self.wave_number - BONUS_WAVE_OFFSET) % 3 == 0:
            print("🎁 Bonus Wave! +2 Max HP")
            if self.player:
                self.player.max_hp += WAVE_BONUS_HP
                self.player.hp += WAVE_BONUS_HP

        enemy_count = random.randint(1, 3)
        for _ in range(enemy_count):
            self.enemies.append(self.spawn_enemy())

        self.wave_number += 1

    # ---------- display helpers ----------
    def display_player_stats(self) -> None:
        if not self.player:
            return
        p = self.player
        print(f"\nKnight {p.name} – HP: {p.hp}/{p.max_hp}  Armour: {p.armour}")
        print(f"Kills: {p.kills}  Crit: {p.crit_chance}%  Level: {p.level}")
        print(f"Score: {p.score}  Score bonus: +{p.score_bonus}")
        for name, cnt in p.upgrades.items():
            if cnt:
                print(f"{name} x{cnt}")

    def display_enemies(self) -> None:
        print("\nENEMIES")
        living = [e for e in self.enemies if e.is_alive()]
        if not living:
            print("None (all cleared)")
            return
        for idx, e in enumerate(living, 1):
            print(f"{idx}. {e.name} – {e.hp}/{e.max_hp} HP (Armour {e.armour})")

    # ---------- enemy selection ----------
    def choose_enemy(self) -> Optional[Enemy]:
        living = [e for e in self.enemies if e.is_alive()]
        if not living:
            return None

        selected = 0
        while True:
            clear_screen()
            self.display_player_stats()
            print("\nSelect target:")
            for i, e in enumerate(living):
                prefix = "> " if i == selected else "  "
                print(f"{prefix}{i+1}. {e.name} – {e.hp}/{e.max_hp} HP")
            print("\nUse w/↑, s/↓, Enter to choose")
            key = get_key()
            norm = key.lower() if len(key) == 1 else key
            if norm == "w" or key == "\x1b[A":
                selected = (selected - 1) % len(living)
            elif norm == "s" or key == "\x1b[B":
                selected = (selected + 1) % len(living)
            elif norm in ("\r", "\n"):
                return living[selected]

    # ---------- upgrades ----------
    def offer_upgrade(self) -> None:
        if not self.player:
            return
        print("\n🎉 LEVEL UP! Choose an upgrade:")
        print("1. +5 Max HP")
        print("2. +1 Damage (min or max)")
        print("3. +2 Armour")
        print("4. +2 Score Bonus")
        print("5. +4% Crit Chance")
        choice = input("Enter 1‑5: ").strip()
        p = self.player
        if choice == "1":
            p.upgrade_hp()
        elif choice == "2":
            p.upgrade_damage()
        elif choice == "3":
            p.upgrade_armour()
        elif choice == "4":
            p.upgrade_score_bonus()
        elif choice == "5":
            p.upgrade_crit()
        else:
            print("Invalid choice – you receive a random upgrade.")
            name = p.apply_random_upgrade()
            print(f"UPGRADED! You got: {name}")

    # ---------- player turn ----------
    SWORD_CMDS = {"sword", "swing", "sword swing", "attack"}

    def player_turn(self) -> None:
        if not self.player:
            return
        while True:
            action = input(
                "\nWhat will you do? (Sword, Recover, Menu, Quit): "
            ).strip().lower()

            # ---------- attack ----------
            if action in self.SWORD_CMDS:
                if not any(e.is_alive() for e in self.enemies):
                    yn = input("No enemies! Swing anyway? (y/n) ").strip().lower()
                    if yn == "y":
                        print("You swing at the empty air.")
                        return
                    continue

                target = self.choose_enemy()
                if not target:
                    print("There are no living enemies.")
                    continue

                dmg, crit = self.player.attack(target)
                if not target.is_alive():
                    print(
                        f"You slayed a {target.name}! (+{target.value} score)"
                    )
                    self.player.score += self.player.score_bonus + target.value
                    self.player.kills += 1

                    # Level‑up / upgrades
                    while self.player.score >= self.next_upgrade_score:
                        self.offer_upgrade()
                        self.next_upgrade_score += UPGRADE_SCORE_STEP
                        self.player.level += 1

                    # Remove dead foes
                    self.enemies = [e for e in self.enemies if e.is_alive()]
                else:
                    msg = f"You hit {target.name} for {dmg} damage"
                    if crit:
                        msg += " (CRITICAL!)"
                    print(msg)
                return

            # ---------- recover ----------
            elif action == "recover":
                if self.player.hp >= self.player.max_hp:
                    yn = input("Already at max HP. Heal anyway? (y/n) ").strip().lower()
                    if yn != "y":
                        continue
                amount = random.randint(RECOVER_MIN, RECOVER_MAX)
                self.player.heal(amount)
                print(
                    f"You recover {amount} HP. ({self.player.hp}/{self.player.max_hp})"
                )
                return

            # ---------- menu ----------
            elif action == "menu":
                choice = self.game_menu()
                if choice == "resume":
                    continue
                if choice == "stats":
                    self.display_player_stats()
                    input("Press Enter to continue...")
                if choice == "quit":
                    self.game_over = True
                    return

            # ---------- quit ----------
            elif action == "quit":
                if input("Really quit? (y/n) ").strip().lower() in ("y", "yes"):
                    self.game_over = True
                    return
                continue

            else:
                print("Invalid action – try: sword, recover, menu, quit")

    # ---------- enemy turn ----------
    def enemy_turn(self) -> None:
        if not self.player:
            return
        for enemy in list(self.enemies):
            if not enemy.is_alive():
                continue

            # Healer may heal an ally
            if isinstance(enemy, Healer) and random.randint(1, 100) <= HEALER_CHANCE:
                target, healed = enemy.heal_ally(self.enemies)
                if target:
                    print(f"{enemy.name} heals {target.name} for {healed} HP!")
                    continue

            # Special attack chance
            if random.random() < SPECIAL_ATTACK_CHANCE:
                dmg = enemy.special_attack(self.player)
                if isinstance(enemy, Goblin):
                    print(f"{enemy.name} uses Sword Swing → {dmg} dmg!")
                elif isinstance(enemy, Ogre):
                    print(f"{enemy.name} uses Powerful Smash → {dmg} dmg!")
                elif isinstance(enemy, Dragon):
                    print(f"{enemy.name} uses Fire Breath → {dmg} dmg!")
                else:
                    print(f"{enemy.name} uses a special attack → {dmg} dmg!")
            else:
                dmg = enemy.attack(self.player)
                print(f"You take {dmg} damage from {enemy.name}!")

    # ---------- game‑over ----------
    def check_game_over(self) -> bool:
        if not self.player or not self.player.is_alive():
            if self.player:
                print("\n💀 GAME OVER! You have been defeated.")
                print(f"Final Score: {self.player.score}")
                print(f"Enemies Slain: {self.player.kills}")

                global highscore, record_holder, highscore_kills
                if self.player.score > highscore:
                    highscore = self.player.score
                    record_holder = self.player.name
                    highscore_kills = self.player.kills
                    save_highscore(highscore, record_holder, highscore_kills)
                    print("🎉 NEW HIGHSCORE!")
                    print(
                        f"{record_holder} now holds the record with {highscore} points!"
                    )
                else:
                    print("You didn't beat the high score.")
                    print(
                        f"Your score: {self.player.score} | High score: {highscore} "
                        f"(held by {record_holder})"
                    )
                self.game_over = True
            return True
        return False

    # ---------- main loop ----------
    def play(self) -> None:
        need_new_wave = True

        while not self.game_over:
            clear_screen()

            if need_new_wave:
                self.spawn_wave()
                need_new_wave = False

            self.display_player_stats()
            self.display_enemies()

            # ----- player turn -----
            self.player_turn()
            if self.game_over:
                break
            if self.check_game_over():
                break

            # ----- enemy turn -----
            if any(e.is_alive() for e in self.enemies):
                print("\n--- Enemy Turn ---")
                self.enemy_turn()
                input("Press Enter to continue...")

            if self.check_game_over():
                break

            # ----- wave finished ? -----
            if not any(e.is_alive() for e in self.enemies):
                need_new_wave = True


# ────────────────────── Entry point ───────────────────────
highscore, record_holder, highscore_kills = load_highscore()


def main() -> None:
    game = Game()
    while True:
        choice = game.start_menu()
        if choice == "start":
            name = input("\nEnter your name: ").strip() or "Knight"
            print(f"Current record: {highscore} points (held by {record_holder})")
            print(f"Knight {name}'s run has started.")
            input("Press Enter to begin...")
            game.init_player(name)
            game.play()
            input("\nPress Enter to return to the main menu...")
        elif choice == "highscores":
            game.show_highscores()
            input("\nPress Enter to return to the main menu...")
        else:   # quit
            print("Thanks for playing Horde Attack!")
            break


if __name__ == "__main__":
    main()

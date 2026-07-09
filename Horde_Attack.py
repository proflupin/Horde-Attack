# ------------------------------------------------------------
# Horde Attack – a text‑based roguelike
# ------------------------------------------------------------

# Imports
import json
import os
import random
import sys
import termios
import tty


# ----------------------------------------------------------------
def get_key() -> str:
    """
    Return a *complete* key code without requiring the user to press Enter.
    - On **Unix** terminals arrow keys generate the 3‑character escape
      sequence ``\x1b[<letter>`` (e.g. ``\x1b[A`` for Up).  We read the
      extra two characters when the first one is ``\x1b``.
    - On **Windows** ``msvcrt.getch()`` returns a two‑byte sequence where
      the second byte is ``b'H'`` (Up), ``b'P'`` (Down), ``b'K'`` (Left),
      or ``b'M'`` (Right).  Those are normalised to the same escape
      strings used on Unix so the rest of the code can stay unchanged.
    """
    try:
        # ----- Windows -------------------------------------------------
        import msvcrt

        first = msvcrt.getch()
        # Arrow / function keys are reported as a prefix (0x00 or 0xE0)
        # followed by a second byte that indicates the key.
        if first in (b"\x00", b"\xe0"):
            second = msvcrt.getch()
            win_to_unix = {
                b"H": "\x1b[A",  # Up
                b"P": "\x1b[B",  # Down
                b"K": "\x1b[D",  # Left
                b"M": "\x1b[C",  # Right
            }
            return win_to_unix.get(second, second.decode())
        else:
            return first.decode()
    except ImportError:
        # ----- Unix / Linux / macOS ------------------------------------
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch += sys.stdin.read(2)   # read the two extra chars
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ----------------------------------------------------------------
# Highscore handling (read/create file)
try:
    with open("highscore.json", "r") as f:
        data = json.load(f)
        highscore = data["highscore"]
        record_holder = data["record_holder"]
        killcount = data["kill_count"]
except (FileNotFoundError, json.JSONDecodeError, KeyError):
    highscore = 0
    killcount = 0
    record_holder = ""
    with open("highscore.json", "w") as f:
        json.dump(
            {
                "highscore": highscore,
                "kill_count": killcount,
                "record_holder": record_holder,
            },
            f,
            indent=4,
        )


# ----------------------------------------------------------------
# PLAYER ---------------------------------------------------------

class Player:
    def __init__(self, name):
        self.name = name
        self.hp = 25
        self.max_hp = 25
        self.armour = 0
        self.min_damage = 1
        self.max_damage = 5
        self.score = 0
        self.score_bonus = 0
        self.upgrades = {
            "Hp Upgrade": 0,
            "Armour Upgrade": 0,
            "Damage Upgrade": 0,
            "Score Upgrade": 0,
            "Crit Upgrade": 0,
        }
        self.kills = 0
        self.crit_chance = 10
        self.level = 0

    def damage(self):
        return random.randint(self.min_damage, self.max_damage)

    def is_alive(self):
        return self.hp > 0

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def take_damage(self, dmg):
        actual = max(0, dmg - self.armour)
        self.hp -= actual
        return actual

    def attack(self, enemy):
        dmg = self.damage()
        crit = random.randint(1, 100) <= self.crit_chance
        if crit:
            actual = int(dmg * 2.5)
            print("CRITICAL HIT!")
        else:
            actual = max(0, dmg - enemy.armour)

        enemy.take_damage(actual)
        return actual, crit

    # ----- Upgrade methods -----------------------------------------
    def upgrade_hp(self):
        self.max_hp += 5
        self.hp += 5
        self.upgrades["Hp Upgrade"] += 1

    def upgrade_damage(self):
        if random.randint(1, 2) == 1:
            self.min_damage += 1
        else:
            self.max_damage += 1
        self.upgrades["Damage Upgrade"] += 1

    def upgrade_armour(self):
        self.armour += 2
        self.upgrades["Armour Upgrade"] += 1

    def upgrade_score_bonus(self):
        self.score_bonus += 2
        self.upgrades["Score Upgrade"] += 1

    def upgrade_crit(self):
        self.crit_chance += 4
        self.upgrades["Crit Upgrade"] += 1

    def apply_random_upgrade(self):
        upgrades = {
            "HP Upgrade": self.upgrade_hp,
            "Damage Upgrade": self.upgrade_damage,
            "Armour Upgrade": self.upgrade_armour,
            "Score Upgrade": self.upgrade_score_bonus,
            "Crit Upgrade": self.upgrade_crit,
        }
        name, func = random.choice(list(upgrades.items()))
        func()
        return name


# ----------------------------------------------------------------
# ENEMIES ---------------------------------------------------------

class Enemy:
    def __init__(self, name, hp, armour, min_damage, max_damage, value):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.armour = armour
        self.min_damage = min_damage
        self.max_damage = max_damage
        self.value = value

    def damage(self):
        return random.randint(self.min_damage, self.max_damage)

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, dmg):
        self.hp -= dmg

    def attack(self, player):
        dmg = self.damage()
        return player.take_damage(dmg)

    def special_attack(self, player):
        return self.attack(player)


class Gremlin(Enemy):
    def __init__(self):
        super().__init__("Gremlin", 1, 0, 1, 1, 1)


class Goblin(Enemy):
    def __init__(self):
        super().__init__("Goblin", 5, 0, 1, 2, 4)

    def special_attack(self, player):
        dmg = self.damage() + 1
        return player.take_damage(dmg)


class Healer(Enemy):
    def __init__(self):
        super().__init__("Healer", 10, 0, 1, 1, 5)

    def heal_enemy(self, enemies):
        """Heal a random wounded ally (excluding self)."""
        candidates = [
            e for e in enemies if e.is_alive() and e != self and e.hp < e.max_hp
        ]
        if not candidates:
            return None, 0
        target = random.choice(candidates)
        heal_amount = 5
        target.hp = min(target.hp + heal_amount, target.max_hp)
        return target, heal_amount


class Ogre(Enemy):
    def __init__(self):
        super().__init__("Ogre", 15, 0, 1, 2, 10)

    def special_attack(self, player):
        dmg = self.damage() * 2
        return player.take_damage(dmg)


class Dragon(Enemy):
    def __init__(self):
        super().__init__("Dragon", 25, 2, 3, 8, 25)

    def special_attack(self, player):
        dmg = self.damage()
        reduced_armour = player.armour // 2
        taken = max(0, dmg - reduced_armour)
        player.hp -= taken
        return taken


# ----------------------------------------------------------------
# GAME LOGIC -------------------------------------------------------

class Game:
    def __init__(self):
        self.player = None
        self.current_enemies = []
        self.next_upgrade_score = 5
        self.wave_number = 1
        self.game_over = False

    # -------------------- Menus ------------------------------------
    def start_menu(self):
        """Main menu – navigation with single‑key presses."""
        options = ["Start New Game", "View Highscores", "Quit"]
        selected = 0

        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("=== HORDE ATTACK ===")
            print(
                "A text‑based roguelike about a knight fighting his way to the castle\n"
            )
            for i, opt in enumerate(options):
                prefix = "> " if i == selected else "  "
                print(f"{prefix}{opt}")

            print("\nUse 'w' / ↑ to move up, 's' / ↓ to move down, Enter to select")
            key = get_key()
            normalized = key.lower() if len(key) == 1 else key

            if normalized == "w" or key == "\x1b[A":
                selected = (selected - 1) % len(options)
            elif normalized == "s" or key == "\x1b[B":
                selected = (selected + 1) % len(options)
            elif normalized in ("\r", "\n"):
                if selected == 0:
                    return "start"
                elif selected == 1:
                    self.show_highscores()
                    input("\nPress Enter to continue...")
                else:
                    return "quit"
            # other keys ignored

    def show_game_menu(self):
        """In‑game pause menu – same navigation style as start_menu."""
        options = ["Resume Game", "View Stats", "Quit Game"]
        selected = 0

        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("=== GAME MENU ===")
            for i, opt in enumerate(options):
                prefix = "> " if i == selected else "  "
                print(f"{prefix}{opt}")

            print("\nUse 'w' / ↑ to move up, 's' / ↓ to move down, Enter to select")
            key = get_key()
            normalized = key.lower() if len(key) == 1 else key

            if normalized == "w" or key == "\x1b[A":
                selected = (selected - 1) % len(options)
            elif normalized == "s" or key == "\x1b[B":
                selected = (selected + 1) % len(options)
            elif key in ("\r", "\n"):
                if selected == 0:
                    return "resume"
                elif selected == 1:
                    self.display_player_stats()
                    input("Press Enter to continue...")
                else:
                    return "quit"
            # ignore other keys

    # -------------------- Highscores -------------------------------
    def show_highscores(self):
        os.system("cls" if os.name == "nt" else "clear")
        print("=== HIGHSCORES ===")
        print(f"Record: {highscore} points (held by {record_holder})")
        if self.player:
            print(f"Your current score: {self.player.score}")

    # -------------------- Player init ------------------------------
    def initialize_player(self, name):
        self.player = Player(name)

    # -------------------- Enemy spawning ----------------------------
    def spawn_enemies(self):
        """Spawn a single enemy with modest scaling."""
        hp_mult = 1 + (self.wave_number * 0.08)
        dmg_mult = 1 + (self.wave_number * 0.05)

        roll = random.randint(1, 100)

        if self.wave_number < 4:          # early
            enemy = Gremlin() if roll <= 60 else Goblin()
        elif self.wave_number < 7:        # mid
            if roll <= 30:
                enemy = Gremlin()
            elif roll <= 80:
                enemy = Goblin()
            else:
                enemy = Ogre()
        elif self.wave_number < 10:       # late
            if roll <= 20:
                enemy = Gremlin()
            elif roll <= 60:
                enemy = Goblin()
            elif roll <= 90:
                enemy = Ogre()
            else:
                enemy = Dragon()
        else:                             # 10+
            if roll <= 10:
                enemy = Gremlin()
            elif roll <= 40:
                enemy = Goblin()
            elif roll <= 70:
                enemy = Ogre()
            else:
                enemy = Dragon()

        # Apply scaling
        enemy.hp = int(enemy.hp * hp_mult)
        enemy.max_hp = enemy.hp
        enemy.min_damage = int(enemy.min_damage * dmg_mult)
        enemy.max_damage = int(enemy.max_damage * dmg_mult)

        self.current_enemies.append(enemy)
        print(f"Spawned {enemy.name}")

    def spawn_wave(self):
        """Create a wave consisting of 1‑3 enemies."""
        print(f"\n--- Wave {self.wave_number} ---")

        if self.wave_number > 1 and self.wave_number % 3 == 1:
            print("🎁 Bonus Wave! You gain +2 Max HP!")
            if self.player:
                self.player.max_hp += 2
                self.player.hp += 2

        count = random.randint(1, 3)
        for _ in range(count):
            self.spawn_enemies()

        self.wave_number += 1

    # -------------------- Display helpers -------------------------
    def display_player_stats(self):
        if not self.player:
            return
        print(f"\nKnight {self.player.name} STATS")
        print(f"HP: {self.player.hp}/{self.player.max_hp}")
        print(f"Kills: {self.player.kills}")
        print(f"Crit chance: {self.player.crit_chance}%")
        print(f"Level: {self.player.level}")
        print(f"Score: {self.player.score}")
        for name, cnt in self.player.upgrades.items():
            if cnt:
                print(f"{name} x{cnt}")

    def display_enemies(self):
        print("\nENEMIES")
        idx = 1
        for e in self.current_enemies:
            if e.is_alive():
                print(f"{idx}. {e.name} – {e.hp}/{e.max_hp} HP")
                idx += 1
        if idx == 1:
            print("None (all cleared)")

    # -------------------- Enemy selection helper -----------------
    # -------------------- Enemy selection helper -----------------
    def choose_enemy(self):
        """Let the player pick a living enemy with w/↑/s/↓/Enter."""
        living = [e for e in self.current_enemies if e.is_alive()]
        if not living:
            return None

        selected = 0
        while True:
            # Clear the terminal and show BOTH the player stats and the enemy list
            os.system("cls" if os.name == "nt" else "clear")
            print("\n=== PLAYER STATS ===")
            # Re‑use the existing method that prints all the stats
            self.display_player_stats()

            print("\nSelect target:")
            for i, e in enumerate(living):
                prefix = "> " if i == selected else "  "
                print(f"{prefix}{i+1}. {e.name} – {e.hp}/{e.max_hp} HP")
            print("\nUse 'w' / ↑ to move, 's' / ↓ to move, Enter to select")

            key = get_key()
            norm = key.lower() if len(key) == 1 else key

            if norm == "w" or key == "\x1b[A":
                selected = (selected - 1) % len(living)
            elif norm == "s" or key == "\x1b[B":
                selected = (selected + 1) % len(living)
            elif key in ("\r", "\n"):
                return living[selected]
            # ignore other keys


    # -------------------- Upgrade handling -----------------------
    def offer_upgrade(self):
        if not self.player:
            return
        print("\n🎉 LEVEL UP! Choose an upgrade:")
        print("1. +5 Max HP")
        print("2. +1 Damage (Min or Max)")
        print("3. +1 Armour")
        print("4. +2 Score Bonus")
        print("5. +3 Crit Chance")
        choice = input("Enter 1‑5: ").strip()
        if choice == "1":
            self.player.upgrade_hp()
        elif choice == "2":
            self.player.upgrade_damage()
        elif choice == "3":
            self.player.upgrade_armour()
        elif choice == "4":
            self.player.upgrade_score_bonus()
        elif choice == "5":
            self.player.upgrade_crit()
        else:
            print("Invalid choice – you receive a random upgrade.")
            name = self.player.apply_random_upgrade()
            print(f"UPGRADED! You got: {name}")

    # -------------------- Player turn -----------------------------
    def player_turn(self):
        if not self.player:
            return
        while True:
            action = (
                input("\nWhat will you do? (Sword, Recover, Menu, Quit): ")
                .strip()
                .lower()
            )

            if action in ("sword", "swing", "sword swing"):
                if not any(e.is_alive() for e in self.current_enemies):
                    yn = input("No enemies! Swing anyway? (y/n) ").strip().lower()
                    if yn == "y":
                        print("You swing at the air.")
                        return
                    continue

                # ---- NEW: interactive enemy selection -----------------
                target_enemy = self.choose_enemy()
                if not target_enemy:
                    print("There are no living enemies.")
                    continue
                # -----------------------------------------------------

                dmg, crit = self.player.attack(target_enemy)
                if not target_enemy.is_alive():
                    print(
                        f"You slayed a {target_enemy.name}! (+{target_enemy.value} score)"
                    )
                    self.player.score += self.player.score_bonus + target_enemy.value
                    self.player.kills += 1

                    while self.player.score >= self.next_upgrade_score:
                        self.offer_upgrade()
                        self.next_upgrade_score += 10
                        self.player.level += 1

                    # Remove dead enemies from the list
                    self.current_enemies = [
                        e for e in self.current_enemies if e.is_alive()
                    ]
                else:
                    msg = f"You hit {target_enemy.name} for {dmg} damage"
                    if crit:
                        msg += " (CRITICAL!)"
                    print(msg)
                return

            elif action == "recover":
                if self.player.hp >= self.player.max_hp:
                    yn = input("Already at max HP. Heal anyway? (y/n) ").strip().lower()
                    if yn != "y":
                        continue
                amount = random.randint(8, 12)
                self.player.heal(amount)
                print(
                    f"You recover {amount} HP. ({self.player.hp}/{self.player.max_hp})"
                )
                return

            elif action == "menu":
                choice = self.show_game_menu()
                if choice == "resume":
                    continue
                if choice == "quit":
                    self.game_over = True
                    return

            elif action == "quit":
                if input("Really quit? (y/n) ").strip().lower() in ("y", "yes"):
                    self.game_over = True
                    return
                continue

            else:
                print("Invalid action – try: sword, recover, menu, quit")

    # -------------------- Enemy turn -----------------------------
    def enemy_turn(self):
        if not self.player:
            return
        for enemy in list(self.current_enemies):
            if not enemy.is_alive():
                continue

            # Healer healing chance
            if isinstance(enemy, Healer) and random.randint(1, 100) <= 75:
                target, healed = enemy.heal_enemy(self.current_enemies)
                if target:
                    print(f"{enemy.name} heals {target.name} for {healed} HP!")
                    continue

            # 25% chance for a special attack
            if random.randint(1, 4) == 1:
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

    # -------------------- Game‑over check ------------------------
    def check_game_over(self):
        if not self.player or not self.player.is_alive():
            if self.player:
                print("\n💀 GAME OVER! You have been defeated.")
                print(f"Final Score: {self.player.score}")
                print(f"Enemies Slain: {self.player.kills}")

                global highscore, record_holder
                if self.player.score > highscore:
                    highscore = self.player.score
                    record_holder = self.player.name
                    with open("highscore.json", "w") as f:
                        json.dump(
                            {
                                "highscore": highscore,
                                "kill_count": self.player.kills,
                                "record_holder": record_holder,
                            },
                            f,
                            indent=4,
                        )
                    print("🎉 NEW HIGHSCORE!")
                    print(
                        f"{record_holder} now holds the record with {highscore} points!"
                    )
                else:
                    print("You didn't beat the high score.")
                    print(
                        f"Your score: {self.player.score} | High score: {highscore} (held by {record_holder})"
                    )
                self.game_over = True
            return True
        return False

    # -------------------- Main game loop -------------------------
    def play(self):
        """Run the game – a new wave starts only when the previous one is cleared."""
        need_new_wave = True

        while not self.game_over:
            os.system("cls" if os.name == "nt" else "clear")

            if need_new_wave:
                self.spawn_wave()
                need_new_wave = False

            self.display_player_stats()
            self.display_enemies()

            # Player turn
            self.player_turn()
            if self.game_over:
                break

            # Check after player action
            if self.check_game_over():
                break

            # Enemy turn (only if any are alive)
            if any(e.is_alive() for e in self.current_enemies):
                print("\n--- Enemy Turn ---")
                self.enemy_turn()
                input("Press Enter to continue...")

            # Check again
            if self.check_game_over():
                break

            # All enemies dead → next wave on next loop
            if not any(e.is_alive() for e in self.current_enemies):
                need_new_wave = True


# ----------------------------------------------------------------
# ENTRY POINT -----------------------------------------------------

def main():
    game = Game()
    while True:
        choice = game.start_menu()
        if choice == "start":
            name = input("\nEnter your name: ").strip() or "Knight"
            print(f"Current record: {highscore} points (held by {record_holder})")
            print(f"Knight {name}'s run has started.")
            input("Press Enter to begin...")

            game.initialize_player(name)
            game.play()

            input("\nPress Enter to return to the main menu...")
        else:   # quit
            print("Thanks for playing Horde Attack!")
            break


if __name__ == "__main__":
    main()

# Python Class Project - Horde Attack with Classes

# A text-based roguelike about a knight fighting his way to the castle
# Horde Attack - Class Version

# Imports
import json
import os
import random

# Highscore management
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
        self.crit_chance = 5
        self.level = 0

    def damage(self):
        return random.randint(self.min_damage, self.max_damage)

    def is_alive(self):
        return self.hp > 0

    def heal(self, amount):
        self.hp = min(self.hp + amount, self.max_hp)

    def take_damage(self, damage):
        actual_damage = max(0, damage - self.armour)
        self.hp -= actual_damage
        return actual_damage

    def attack(self, enemy):
        damage = self.damage()
        crit = random.randint(1, 100) <= self.crit_chance

        if crit:
            actual_damage = damage * 2
            print("CRITICAL HIT!")
        else:
            actual_damage = max(0, damage - enemy.armour)

        enemy.take_damage(actual_damage)
        return actual_damage, crit

    def upgrade_hp(self):
        self.max_hp += 5
        self.hp += 5
        self.upgrades["Hp Upgrade"] += 1

    def upgrade_damage(self):
        which1 = random.randint(1, 2)
        if which1 == 1:
            self.min_damage += 1
        else:
            self.max_damage += 1
        self.upgrades["Damage Upgrade"] += 1

    def upgrade_armour(self):
        self.armour += 1
        self.upgrades["Armour Upgrade"] += 1

    def upgrade_score_bonus(self):
        self.score_bonus += 2
        self.upgrades["Score Upgrade"] += 1

    def upgrade_crit(self):
        self.crit_chance += 3
        self.upgrades["Crit Upgrade"] += 1

    def apply_random_upgrade(self):
        upgrades = {
            "HP Upgrade": self.upgrade_hp,
            "Damage Upgrade": self.upgrade_damage,
            "Armour Upgrade": self.upgrade_armour,
            "Score Upgrade": self.upgrade_score_bonus,
            "Crit Upgrade": self.upgrade_crit,
        }
        upgrade_name, func = random.choice(list(upgrades.items()))
        func()
        return upgrade_name


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

    def take_damage(self, damage):
        self.hp -= damage

    def attack(self, player):
        damage = self.damage()
        damage_taken = player.take_damage(damage)
        return damage_taken

    def special_attack(self, player):
        # Default enemy does a normal attack
        return self.attack(player)


class Gremlin(Enemy):
    def __init__(self):
        super().__init__("Gremlin", 1, 0, 1, 1, 1)

    def special_attack(self, player):
        # Gremlin does nothing special, just a weak attack
        return self.attack(player)


class Goblin(Enemy):
    def __init__(self):
        super().__init__("Goblin", 5, 0, 1, 2, 4)

    def special_attack(self, player):
        # Goblin has a sword swing that does slightly more damage
        damage = self.damage() + 1  # Slightly more damage
        damage_taken = player.take_damage(damage)
        return damage_taken


class Healer(Enemy):
    def __init__(self):
        super().__init__("Healer", 6, 0, 1, 1, 5)

    def special_attack(self, player):
        # Healer does a normal attack
        return self.attack(player)

    def heal_enemy(self, enemies):
        # Healer can heal other enemies
        alive_enemies = [e for e in enemies if e.is_alive() and e != self]
        if alive_enemies:
            target = random.choice(alive_enemies)
            heal_amount = random.randint(1, 3)
            target.hp = min(target.hp + heal_amount, target.max_hp)
            return target, heal_amount
        return None, 0


class Ogre(Enemy):
    def __init__(self):
        super().__init__("Ogre", 15, 0, 1, 2, 10)

    def special_attack(self, player):
        # Ogre has a powerful smash attack that does double damage
        damage = self.damage() * 2
        damage_taken = player.take_damage(damage)
        return damage_taken


class Dragon(Enemy):
    def __init__(self):
        super().__init__("Dragon", 20, 2, 3, 5, 20)

    def special_attack(self, player):
        # Dragon has fire breath that ignores half armor
        damage = self.damage()
        reduced_armour = player.armour // 2
        damage_taken = max(0, damage - reduced_armour)
        player.hp -= damage_taken
        return damage_taken


class Game:
    def __init__(self):
        self.player = None
        self.current_enemies = []
        self.next_upgrade_score = 10
        self.wave_number = 1
        self.game_over = False
        self.enemy_counter = 1  # Track unique enemy numbers
        self.enemy_numbers = {}  # Map enemy objects to their numbers

    def start_menu(self):
        os.system("cls" if os.name == "nt" else "clear")
        print("=== HORDE ATTACK ===")
        print("A text-based roguelike about a knight fighting his way to the castle\n")
        print("1. Start New Game")
        print("2. View Highscores")
        print("3. Quit")

        while True:
            choice = input("\nEnter your choice (1-3): ").strip()
            if choice == "1":
                return "start"
            elif choice == "2":
                self.show_highscores()
                input("\nPress Enter to continue...")
            elif choice == "3":
                return "quit"
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def show_highscores(self):
        os.system("cls" if os.name == "nt" else "clear")
        print("=== HIGHSCORES ===")
        print(f"Record: {highscore} points (held by {record_holder})")
        if self.player:
            print(f"Your current score: {self.player.score}")

    def initialize_player(self, name):
        self.player = Player(name)

    def spawn_enemies(self):
        # Reduced enemy scaling - less aggressive
        hp_mult = 1 + (self.wave_number * 0.08)  # Changed from 0.15 to 0.08
        dmg_mult = 1 + (self.wave_number * 0.05)  # Added damage scaling

        # Spawn logic with scaling
        which1 = random.randint(1, 100)
        if self.wave_number < 5:
            # Early waves: mostly weak enemies
            if which1 <= 60:
                enemy = Gremlin()
                print("Spawned Gremlin")
            else:
                enemy = Goblin()
                print("Spawned Goblin")
        elif self.wave_number < 9:
            # Mid waves: mix
            if which1 <= 30:
                enemy = Gremlin()
                print("Spawned Gremlin")
            elif which1 <= 80:
                enemy = Goblin()
                print("Spawned Goblin")
            else:
                enemy = Ogre()
                print("Spawned Ogre")
        else:
            # Late waves: tougher spawns
            if which1 <= 20:
                enemy = Gremlin()
                print("Spawned Gremlin")
            elif which1 <= 60:
                enemy = Goblin()
                print("Spawned Goblin")
            elif which1 <= 90:
                enemy = Ogre()
                print("Spawned Ogre")
            else:
                enemy = Dragon()
                print("Spawned Dragon!!!")

        # Scale enemy stats
        enemy.hp = int(enemy.hp * hp_mult)
        enemy.max_hp = enemy.hp
        enemy.min_damage = int(enemy.min_damage * dmg_mult)
        enemy.max_damage = int(enemy.max_damage * dmg_mult)

        # Assign persistent enemy number
        self.enemy_numbers[enemy] = self.enemy_counter
        self.enemy_counter += 1

        self.current_enemies.append(enemy)

    def spawn_wave(self):
        print(f"\n--- Wave {self.wave_number} ---")

        # Wave bonus every 3 waves
        if self.wave_number > 1 and self.wave_number % 3 == 1:
            print("🎁 Bonus Wave! You gain +2 Max HP!")
            if self.player:
                self.player.max_hp += 2
                self.player.hp += 2

        # Always spawn 1-2 enemies, max 5 total
        amount = min(2, 5 - len(self.current_enemies))  # Don't exceed 5
        for _ in range(amount):
            self.spawn_enemies()
        self.wave_number += 1

    def display_player_stats(self):
        if self.player:
            print(f"\nKnight {self.player.name} STATS")
            print(f"You have {self.player.hp}/{self.player.max_hp} HP")
            print(f"Kill count = {self.player.kills}")
            print(f"Crit chance = {self.player.crit_chance}%")
            print(f"Level = {self.player.level}")
            print(f"Current Score = {self.player.score}")
            for upgrade_name, count in self.player.upgrades.items():
                if count > 0:
                    print(f"{upgrade_name} x{count}")

    def display_enemies(self):
        print("\nENEMIES")
        for enemy in self.current_enemies:
            if enemy.is_alive():
                print(
                    f"{self.enemy_numbers[enemy]}. {enemy.name} - {enemy.hp}/{enemy.max_hp} HP"
                )

    def offer_upgrade(self):
        if not self.player:
            return

        print("\n🎉 LEVEL UP! Choose an upgrade:")
        print("1. +5 Max HP")
        print("2. +1 Damage (Min or Max)")
        print("3. +1 Armour")
        print("4. +2 Score Bonus")
        print("5. +3 Crit Chance")

        choice = input("Enter 1-5: ").strip()
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
            print("Invalid choice. You gain a random upgrade.")
            upgrade_name = self.player.apply_random_upgrade()
            print(f"\nUPGRADE! You gained {upgrade_name}")

    def player_turn(self):
        if not self.player:
            return

        while True:
            action = (
                input("\nWhat will you do? (Sword, Recover, Menu, or Quit): ")
                .strip()
                .lower()
            )

            if action in ("sword", "swing", "sword swing"):
                # Check if there are enemies to attack
                if not any(e.is_alive() for e in self.current_enemies):
                    yes_no = input("No enemies! Swing anyway? y/n ").strip().lower()
                    if yes_no == "y":
                        print("You swing at the air")
                        return
                    elif yes_no == "n":
                        continue
                    else:
                        print("Invalid input.")
                        continue

                # Choose which enemy to attack
                target = input(
                    "Swing your sword at which enemy? Enter number: "
                ).strip()

                # Check if the input is a number
                if not target.isdigit():
                    print("Invalid input.")
                    continue

                # Find enemy by enemy_number instead of index
                target_number = int(target)
                enemy = None

                for e in self.current_enemies:
                    if self.enemy_numbers[e] == target_number and e.is_alive():
                        enemy = e
                        break

                # If enemy not found or not alive
                if enemy is None:
                    print("That enemy doesn't exist or is already dead.")
                    continue

                # Attack the enemy
                damage, crit = self.player.attack(enemy)

                # Check if the enemy dies
                if not enemy.is_alive():
                    print(f"You slayed a {enemy.name}! Good job!")
                    self.player.score += self.player.score_bonus + enemy.value
                    self.player.kills += 1

                    if self.player.kills >= 100:
                        print("You have won! Continue?")
                        yes_no = input("y/n? ")
                        if yes_no.lower() == "n":
                            print("You have quit! You can close this now.")
                            self.game_over = True
                            return

                    while self.player.score >= self.next_upgrade_score:
                        self.offer_upgrade()
                        self.next_upgrade_score += 10
                        self.player.level += 1

                        # Remove dead enemies from the list and clean up enemy numbers
                        alive_enemies = [
                            e for e in self.current_enemies if e.is_alive()
                        ]
                        # Clean up enemy numbers dictionary
                        dead_enemies = [
                            e for e in self.current_enemies if not e.is_alive()
                        ]
                        for dead_enemy in dead_enemies:
                            if dead_enemy in self.enemy_numbers:
                                del self.enemy_numbers[dead_enemy]
                        self.current_enemies = alive_enemies
                else:
                    if crit:
                        print(
                            f"You hit {enemy.name} for {damage} damage! (Critical Hit)"
                        )
                    else:
                        print(f"You hit {enemy.name} for {damage} damage!")

                return

            elif action == "recover":
                # Check if the player is at max health
                if self.player.hp >= self.player.max_hp:
                    yes_no = (
                        input("You're already at max HP. Heal anyway? y/n ")
                        .strip()
                        .lower()
                    )
                    if yes_no == "y":
                        print("You catch your breath and heal....none")
                        return
                    elif yes_no == "n":
                        print("You decide to use your time more wisely.")
                        continue
                    else:
                        print("Try again! Must've had a typo :)")
                        continue
                else:
                    amount_healed = random.randint(1, 3)
                    self.player.heal(amount_healed)
                    print(f"You catch your breath and heal {amount_healed}")
                    print(f"You are now at {self.player.hp}/{self.player.max_hp} HP")
                    return

            elif action == "menu":
                menu_choice = self.show_game_menu()
                if menu_choice == "resume":
                    continue
                elif menu_choice == "quit":
                    self.game_over = True
                    return

            elif action == "quit":
                confirm = (
                    input("Are you sure you want to quit? (y/n): ").strip().lower()
                )
                if confirm in ("y", "yes"):
                    self.game_over = True
                    return
                else:
                    continue

            else:
                print("Invalid action. Try: sword, recover, menu, or quit")

    def show_game_menu(self):
        print("\n=== GAME MENU ===")
        print("1. Resume Game")
        print("2. View Stats")
        print("3. Quit Game")

        while True:
            choice = input("Enter your choice (1-3): ").strip()
            if choice == "1":
                return "resume"
            elif choice == "2":
                self.display_player_stats()
                input("Press Enter to continue...")
            elif choice == "3":
                return "quit"
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def enemy_turn(self):
        if not self.player:
            return

        # Process each enemy's turn
        for enemy in self.current_enemies[
            :
        ]:  # Use a copy to avoid modification during iteration
            if not enemy.is_alive():
                continue

            # Healer special behavior
            if isinstance(enemy, Healer):
                # 50% chance to heal another enemy, 50% to attack
                if random.randint(1, 2) == 1:
                    target, heal_amount = enemy.heal_enemy(self.current_enemies)
                    if target:
                        print(
                            f"{enemy.name} healed {target.name} for {heal_amount} HP!"
                        )
                        continue  # Skip normal attack
                    # If no target to heal, fall through to normal attack
                # If not healing, do normal attack

            # Randomly choose between normal attack and special attack
            if random.randint(1, 3) == 1:  # 33% chance for special attack
                damage_taken = enemy.special_attack(self.player)
                if isinstance(enemy, Goblin):
                    print(
                        f"{enemy.name} used Sword Swing and dealt {damage_taken} damage!"
                    )
                elif isinstance(enemy, Ogre):
                    print(
                        f"{enemy.name} used Powerful Smash and dealt {damage_taken} damage!"
                    )
                elif isinstance(enemy, Dragon):
                    print(
                        f"{enemy.name} used Fire Breath and dealt {damage_taken} damage!"
                    )
                else:
                    print(
                        f"{enemy.name} used a special attack and dealt {damage_taken} damage!"
                    )
            else:
                # Normal attack
                damage_taken = enemy.attack(self.player)
                print(f"You took {damage_taken} damage from {enemy.name}!")

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
                    print("You didn't quite beat the high score!")
                    print(
                        f"Your score: {self.player.score} | High score: {highscore} | Held by: {record_holder}"
                    )

                self.game_over = True
                return True
        return False

    def play(self):
        # Main game loop
        while not self.game_over:
            # Clear screen for readability
            os.system("cls" if os.name == "nt" else "clear")

            # Display player stats
            self.display_player_stats()

            # Spawn wave if needed
            if not any(e.is_alive() for e in self.current_enemies):
                self.spawn_wave()

            # Display enemies
            self.display_enemies()

            # Player turn
            self.player_turn()
            if self.game_over:
                break

            # Check if game is over after player turn
            if self.check_game_over():
                break

            # Enemy turn
            if any(e.is_alive() for e in self.current_enemies):
                print("\n--- Enemy Turn ---")
                self.enemy_turn()
                input("Press Enter to continue...")

            # Check if game is over after enemy turn
            if self.check_game_over():
                break


# Main game execution
def main():
    game = Game()

    while True:
        choice = game.start_menu()

        if choice == "start":
            name = input("\nPlease enter your name: ").strip()
            if not name:
                name = "Knight"

            print(f"Current record: {highscore} points (held by {record_holder})")
            print(f"Knight {name}'s run has started.")
            input("Press Enter to begin your quest...")

            game.initialize_player(name)
            game.play()

            # After game over, return to main menu
            input("\nPress Enter to return to the main menu...")

        elif choice == "quit":
            print("Thanks for playing Horde Attack!")
            break


if __name__ == "__main__":
    main()

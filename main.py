import sys
import math
import random
import pygame
import asyncio  # ─── ADDED FOR WEBASSEMBLY / GITHUB PAGES COMPATIBILITY ───

# 1. ENGINE INITIALIZATION & CANVAS SCREEN SETUP
pygame.init()
pygame.mixer.init(44100, -16, 2, 512) 

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("ROK-STRIKER: WEB COMMAND")
clock = pygame.time.Clock()

# ─── 2. CYBERPUNK NEON COLOR PALETTE ──────────────────────────────────────
COLOR_BG = (10, 8, 20)         
COLOR_PLAYER = (0, 255, 200)    
COLOR_ENEMY = (255, 50, 50)     
COLOR_LASER = (255, 255, 0)     
COLOR_GRID = (28, 24, 48)       
COLOR_TEXT = (240, 240, 255)    
COLOR_METRIC = (0, 180, 255)    
COLOR_JOYSTICK = (100, 100, 120)

font_hud = pygame.font.SysFont("Courier", 18, bold=True)
font_big = pygame.font.SysFont("Courier", 38, bold=True)

# ─── 3. PROCEDURAL SOUND SYNTHESIZER ENGINE ──────────────────────────────
def generate_synth_sound(frequency_start, frequency_end, duration_ms, wave_type="sine"):
    sample_rate = 44100
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    buffer = bytearray()
    
    for i in range(num_samples):
        t = i / sample_rate
        fraction = i / num_samples
        current_freq = frequency_start + (frequency_end - frequency_start) * fraction
        value = math.sin(2 * math.pi * current_freq * t)
        
        if wave_type == "square":
            value = 1.0 if value >= 0 else -1.0
            
        fade_out = 1.0 - fraction
        sample = int(value * 32767 * 0.3 * fade_out)
        
        try:
            buffer.extend(sample.to_bytes(2, byteorder='little', signed=True)) 
            buffer.extend(sample.to_bytes(2, byteorder='little', signed=True)) 
        except Exception:
            buffer.extend((0).to_bytes(4, byteorder='little'))

    return pygame.mixer.Sound(buffer=bytes(buffer))

sound_laser = generate_synth_sound(880, 440, 120, "sine")     
sound_explosion = generate_synth_sound(120, 30, 250, "square") 
sound_defeat = generate_synth_sound(400, 80, 600, "sine")      

# ─── 4. CORE ENTITY GAME STATE METRICS ───────────────────────────────────
player_x = 100
player_y = SCREEN_HEIGHT // 2
player_base_speed = 7.0  
player_width = 45
player_height = 24

player_lasers = []  
enemies = []         
starfield = []       

for _ in range(50):
    starfield.append([random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT), random.uniform(1.5, 4.5)])

core_score = 0
high_score = 0
kills = 0             
best_kill_rate = 0.0  
survival_time = 0.0   

enemy_spawn_timer = 0.0
laser_cooldown_timer = 0.0
game_over = False

# ─── 5. MOBILE VIRTUAL JOYSTICK PARAMS ───────────────────────────────────
JOYSTICK_CENTER = (120, SCREEN_HEIGHT - 120)
JOYSTICK_BASE_RADIUS = 60
JOYSTICK_KNOB_RADIUS = 25
joystick_knob_pos = list(JOYSTICK_CENTER)
joystick_active = False
joystick_vector = [0.0, 0.0]  

# ─── 6. CORE ENGINE SIMULATION LOOP WRAPPED FOR WEBASSEMBLY ───────────────
async def main():
    # Declare globals so the async function scope can mutate parameters smoothly
    global player_x, player_y, core_score, high_score, kills, best_kill_rate, survival_time
    global enemy_spawn_timer, laser_cooldown_timer, game_over, joystick_active, joystick_knob_pos, joystick_vector
    
    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # A. CROSS-PLATFORM INPUT HANDLER
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = event.pos
                else: 
                    mouse_pos = (int(event.x * SCREEN_WIDTH), int(event.y * SCREEN_HEIGHT))

                if game_over:
                    # INSTANT RESET
                    player_x = 100
                    player_y = SCREEN_HEIGHT // 2
                    player_lasers.clear()
                    enemies.clear()
                    core_score = 0
                    kills = 0
                    survival_time = 0.0
                    joystick_active = False
                    joystick_knob_pos = list(JOYSTICK_CENTER)
                    joystick_vector = [0.0, 0.0]
                    game_over = False
                else:
                    dist_to_joystick = math.hypot(mouse_pos[0] - JOYSTICK_CENTER[0], mouse_pos[1] - JOYSTICK_CENTER[1])
                    if dist_to_joystick <= JOYSTICK_BASE_RADIUS + 10:
                        joystick_active = True

            elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                joystick_active = False
                joystick_knob_pos = list(JOYSTICK_CENTER)
                joystick_vector = [0.0, 0.0]

            elif event.type in (pygame.MOUSEMOTION, pygame.FINGERMOTION):
                if joystick_active:
                    if event.type == pygame.MOUSEMOTION:
                        motion_pos = event.pos
                    else:
                        motion_pos = (int(event.x * SCREEN_WIDTH), int(event.y * SCREEN_HEIGHT))
                    
                    dx = motion_pos[0] - JOYSTICK_CENTER[0]
                    dy = motion_pos[1] - JOYSTICK_CENTER[1]
                    distance = math.hypot(dx, dy)
                    
                    if distance == 0:
                        joystick_vector = [0.0, 0.0]
                        joystick_knob_pos = list(JOYSTICK_CENTER)
                    else:
                        clamp_dist = min(distance, JOYSTICK_BASE_RADIUS)
                        joystick_vector = [dx / distance, dy / distance] 
                        
                        power_ratio = clamp_dist / JOYSTICK_BASE_RADIUS
                        joystick_vector[0] *= power_ratio
                        joystick_vector[1] *= power_ratio
                        
                        joystick_knob_pos[0] = JOYSTICK_CENTER[0] + (dx / distance) * clamp_dist
                        joystick_knob_pos[1] = JOYSTICK_CENTER[1] + (dy / distance) * clamp_dist

        # B. SIMULATION & MOVEMENT PROCESSING
        if not game_over:
            survival_time += dt  

            # Apply virtual touch pad input movements
            player_x += joystick_vector[0] * player_base_speed
            player_y += joystick_vector[1] * player_base_speed

            # PC Keyboard fallback mappings
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w] or keys[pygame.K_UP]:    player_y -= player_base_speed
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:  player_y += player_base_speed
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:  player_x -= player_base_speed
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: player_x += player_base_speed

            player_x = max(15, min(SCREEN_WIDTH // 2, player_x)) 
            player_y = max(60, min(SCREEN_HEIGHT - 45, player_y)) 

            # Laser Cooldown Check
            laser_cooldown_timer += dt
            if laser_cooldown_timer >= 0.16:  
                laser_cooldown_timer = 0.0
                player_lasers.append([int(player_x + player_width), int(player_y + player_height // 2)])
                sound_laser.play() 

            # Background Star field scroll
            for star in starfield:
                star[0] -= star[2]  
                if star[0] < 0:
                    star[0] = SCREEN_WIDTH
                    star[1] = random.randint(0, SCREEN_HEIGHT)

            # Enemy Rocket Spawner Clock
            enemy_spawn_timer += dt
            spawn_rate = max(0.22, 0.75 - (core_score * 0.02))
            if enemy_spawn_timer >= spawn_rate:
                enemy_spawn_timer = 0.0
                ex = SCREEN_WIDTH + 40
                ey = random.randint(70, SCREEN_HEIGHT - 60)
                espeed = random.uniform(3.5, 6.5) + (core_score * 0.12)
                enemies.append([[ex, ey], espeed])

            # Move active lasers
            for laser in player_lasers[:]:
                laser[0] += 13.0  
                if laser[0] > SCREEN_WIDTH:
                    player_lasers.remove(laser)

            # Threat tracking and collision calculation
            for enemy in enemies[:]:
                ex, ey = enemy[0]
                espeed = enemy[1]
                enemy[0][0] -= espeed
                
                if ex < -50:
                    enemies.remove(enemy)
                    core_score += 1  
                    continue

                for laser in player_lasers[:]:
                    lx, ly = laser
                    if ex <= lx <= ex + 40 and ey <= ly <= ey + 24:
                        sound_explosion.play() 
                        if enemy in enemies: enemies.remove(enemy)
                        if laser in player_lasers: player_lasers.remove(laser)
                        core_score += 2  
                        kills += 1  
                        break

                if (ex <= player_x + player_width and ex + 40 >= player_x and
                    ey <= player_y + player_height and ey + 24 >= player_y):
                    sound_defeat.play() 
                    game_over = True
                    if core_score > high_score:
                        high_score = core_score

            # Performance dashboard analytics math update
            if survival_time > 1.0:
                current_kill_rate = (kills / survival_time) * 60.0
                if current_kill_rate > best_kill_rate:
                    best_kill_rate = current_kill_rate
            else:
                current_kill_rate = 0.0

        # C. GRAPHIC RENDER ENGINE
        screen.fill(COLOR_BG)

        # Draw Cyber Grid Background
        for x in range(0, SCREEN_WIDTH, 60):
            pygame.draw.line(screen, COLOR_GRID, (x, 0), (x, SCREEN_HEIGHT), 1)
        for y in range(0, SCREEN_HEIGHT, 60):
            pygame.draw.line(screen, COLOR_GRID, (0, y), (SCREEN_WIDTH, y), 1)

        # Draw stars
        for star in starfield:
            pygame.draw.circle(screen, (120, 120, 180), (int(star[0]), int(star[1])), int(star[2] // 1.5))

        # Draw lasers
        for laser in player_lasers:
            pygame.draw.line(screen, COLOR_LASER, (laser[0], laser[1]), (laser[0] + 18, laser[1]), 3)

        # Draw Enemy Rockets
        for enemy in enemies:
            ex, ey = enemy[0]
            pygame.draw.rect(screen, COLOR_ENEMY, (int(ex + 10), int(ey), 30, 24), border_radius=4)
            pygame.draw.polygon(screen, COLOR_ENEMY, [(int(ex + 10), int(ey)), (int(ex), int(ey + 12)), (int(ex + 10), int(ey + 24))])
            pygame.draw.rect(screen, (160, 30, 60), (int(ex + 32), int(ey - 6), 8, 36), border_radius=2)
            pygame.draw.polygon(screen, (255, 150, 0), [(int(ex + 40), int(ey + 6)), (int(ex + 52), int(ey + 12)), (int(ex + 40), int(ey + 18))])

        if not game_over:
            # Draw Player Rocket with animated exhaust particle vectors
            pygame.draw.polygon(screen, (255, 100, 0), [(int(player_x), int(player_y + 4)), (int(player_x - 16), int(player_y + 12)), (int(player_x), int(player_y + 20))])
            pygame.draw.polygon(screen, (255, 220, 0), [(int(player_x), int(player_y + 7)), (int(player_x - 10), int(player_y + 12)), (int(player_x), int(player_y + 17))])

            pygame.draw.rect(screen, COLOR_PLAYER, (int(player_x), int(player_y), 32, player_height), border_radius=4)
            pygame.draw.polygon(screen, COLOR_PLAYER, [(int(player_x + 32), int(player_y)), (int(player_x + player_width), int(player_y + 12)), (int(player_x + 32), int(player_y + player_height))])
            pygame.draw.rect(screen, (0, 160, 140), (int(player_x), int(player_y - 6), 8, 36), border_radius=2)
            pygame.draw.ellipse(screen, (255, 255, 255), (int(player_x + 16), int(player_y + 5), 12, 14))

            # Render Virtual Joystick HUD Element
            pygame.draw.circle(screen, (40, 40, 55, 120), JOYSTICK_CENTER, JOYSTICK_BASE_RADIUS)
            pygame.draw.circle(screen, COLOR_JOYSTICK, JOYSTICK_CENTER, JOYSTICK_BASE_RADIUS, 3)
            pygame.draw.circle(screen, COLOR_PLAYER if joystick_active else COLOR_JOYSTICK, (int(joystick_knob_pos[0]), int(joystick_knob_pos[1])), JOYSTICK_KNOB_RADIUS)

            # Render Performance Hud analytics dashboard
            pygame.draw.rect(screen, (5, 4, 10), (0, 0, SCREEN_WIDTH, 50))
            pygame.draw.line(screen, COLOR_GRID, (0, 50), (SCREEN_WIDTH, 50), 2)

            score_lbl = font_hud.render(f"SCORE: {core_score}", True, COLOR_TEXT)
            screen.blit(score_lbl, (25, 16))

            rate_lbl = font_hud.render(f"KILL RATE: {current_kill_rate:.1f}/MIN", True, COLOR_METRIC)
            best_lbl = font_hud.render(f"BEST RATE: {best_kill_rate:.1f}/MIN", True, COLOR_LASER)
            
            screen.blit(rate_lbl, (290, 16))
            screen.blit(best_lbl, (610, 16))
        else:
            # RENDER GAME OVER REBOOT DATA SCREEN
            msg_1 = font_big.render("ROCKET HULL DESTROYED", True, COLOR_ENEMY)
            msg_2 = font_hud.render(f"TOTAL THREAT SCORE ELIMINATED: {core_score}", True, COLOR_TEXT)
            msg_analytics = font_hud.render(f"PEAK EFFICIENCY RECORD SECURED: {best_kill_rate:.1f} KILLS/MIN", True, COLOR_METRIC)
            msg_4 = font_big.render("[ TAP / CLICK SCREEN TO RESPAWN ]", True, COLOR_PLAYER)

            screen.blit(msg_1, (SCREEN_WIDTH // 2 - msg_1.get_width() // 2, 160))
            screen.blit(msg_2, (SCREEN_WIDTH // 2 - msg_2.get_width() // 2, 240))
            screen.blit(msg_analytics, (SCREEN_WIDTH // 2 - msg_analytics.get_width() // 2, 280))
            screen.blit(msg_4, (SCREEN_WIDTH // 2 - msg_4.get_width() // 2, 400))

        pygame.display.flip()
        
        # ─── CRITICAL FOR WEBASSEMBLY: Yield control back to browser frame thread ───
        await asyncio.sleep(0)

# Kickstart the container thread wrapper
asyncio.run(main())

# Scout Dog Walk Hackathon Pitch

## One-line

We turn a bare Scout Mini chassis into a supervised "dog walking" companion: a predictable, low-speed robot that can lead a short route, stop safely, and make the care task visible in a live demo.

## What We Actually Built

- A ROS 2 Jazzy control package for Scout Mini.
- A browser control console with route, speed, start, pause, and emergency stop.
- A route state machine that publishes `/cmd_vel` to the AgileX `scout_base_node`.
- A rosbridge link so the web UI can talk to ROS 2 topics.
- A public story page for the hackathon demo.

## What It Is Not

- It is not autonomous navigation.
- It is not a production pet-care product.
- It is not safe to expose raw robot control to the public internet.
- It does not claim obstacle avoidance unless external sensors are added.

## Demo Story

The core story is not "we solved dog walking." The story is:

> A lot of care work is repetitive, physical, and invisible. With only a mobile chassis and one hackathon day, we built the smallest honest version of a robotic helper: a supervised companion that can take a repeated route and let a human stay in control.

The Scout Mini behaves like a disciplined walking partner:

1. The operator connects the web console to the robot.
2. The operator chooses a route: short potty walk, neighborhood loop, or park stroll.
3. The operator sets a slow speed.
4. The robot walks the route.
5. The operator can pause or emergency-stop immediately.

## Live Demo Flow

1. Show the physical Scout Mini and the mounted leash/identity/phone holder if available.
2. Open the web console.
3. Connect to `ws://robot-ip:9090`.
4. Choose `小区散步` for the clearest route demo, or `短途如厕` if the floor area is tight.
5. Start at low speed.
6. Pause mid-route to show human supervision.
7. Resume, then emergency stop.
8. Show the architecture slide: browser -> rosbridge -> dog_walk_node -> `/cmd_vel` -> `scout_base_node` -> CAN -> Scout Mini.

## App Scope After Cleanup

The demo should keep these controls:

- Connect/disconnect robot.
- Route selection.
- Speed limit.
- Start.
- Pause/resume.
- Emergency stop.
- Status display.

Do not add complex features before the presentation unless they improve reliability:

- No login system.
- No cloud remote control by default.
- No fake AI autonomy.
- No sensor claims without hardware.

## Deployment Boundary

The robot computer must run:

- `scout_base_node`
- `rosbridge_server`
- `dog_walk_node.py`
- local web server, if controlling on the same network

The public server should run:

- story page
- static copy of the web UI
- optional protected proxy in the future

The public server should not directly expose rosbridge or `/cmd_vel`.

## Closing Line

This is a robot that makes an invisible care routine visible. The value of the demo is not full autonomy; it is a working, honest bridge from a physical chassis to a human-supervised care workflow.

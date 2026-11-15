import gc
import pyglet
from pyglet import gl
import traceback
import time

from cartridge import CartridgeParser
from memory import TICMemory
from graphics import TICGraphics, WIDTH, HEIGHT
from input import TICInput
from audio import TICAudio
from api import TICAPI


class TIC80Runtime:

    def __init__(self, filename):

        self.filename = filename
        self.game = None
        self.running = True
        self.paused = False
        self.frame_count = 0
        self.start_time = time.monotonic()
        self.error = None

        config = pyglet.gl.Config(double_buffer=True)

        self.window = pyglet.window.Window(
            width=WIDTH * 3,
            height=HEIGHT * 3,
            caption="TICPY Runtime",
            resizable=True,
            vsync=False,
            config=config
        )

        self.window.set_minimum_size(WIDTH, HEIGHT)
        self.window.set_mouse_visible(False)

        self.memory = TICMemory()
        self.graphics = TICGraphics(self.memory)
        self.input = TICInput()
        self.audio = TICAudio(self.memory)

        self._install_events()
        self.load_game(filename)

        gc.set_threshold(50000, 20, 20)
        pyglet.clock.schedule_interval(self.update, 1.0 / 60.0)

    def _install_events(self):

        @self.window.event
        def on_key_press(symbol, modifiers):
            if symbol == pyglet.window.key.ESCAPE:
                self.stop()
                return
            if symbol == pyglet.window.key.F11:
                self.window.set_fullscreen(not self.window.fullscreen)
                return
            if symbol == pyglet.window.key.F2:
                self.load_game(self.filename)
                return
            self.input.key_down(symbol)

        @self.window.event
        def on_key_release(symbol, modifiers):
            self.input.key_up(symbol)

        @self.window.event
        def on_mouse_motion(x, y, dx, dy):
            self._update_mouse(x, y)

        @self.window.event
        def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            self._update_mouse(x, y)

        @self.window.event
        def on_mouse_press(x, y, button, modifiers):
            self._update_mouse(x, y)
            if button == pyglet.window.mouse.LEFT:
                self.input.mouse_left = True
            elif button == pyglet.window.mouse.MIDDLE:
                self.input.mouse_middle = True
            elif button == pyglet.window.mouse.RIGHT:
                self.input.mouse_right = True

        @self.window.event
        def on_mouse_release(x, y, button, modifiers):
            if button == pyglet.window.mouse.LEFT:
                self.input.mouse_left = False
            elif button == pyglet.window.mouse.MIDDLE:
                self.input.mouse_middle = False
            elif button == pyglet.window.mouse.RIGHT:
                self.input.mouse_right = False

        @self.window.event
        def on_mouse_scroll(x, y, scroll_x, scroll_y):
            self.input.scroll_x = scroll_x
            self.input.scroll_y = scroll_y

        @self.window.event
        def on_draw():
            self.window.clear()
            self._draw_game()

    def _get_screen_rect(self):
        fb_w, fb_h = self.window.get_framebuffer_size()
        fb_w, fb_h = max(1, fb_w), max(1, fb_h)
        scale = min(fb_w / WIDTH, fb_h / HEIGHT)
        vp_w = int(WIDTH * scale)
        vp_h = int(HEIGHT * scale)
        vp_x = (fb_w - vp_w) // 2
        vp_y = (fb_h - vp_h) // 2
        return vp_x, vp_y, vp_w, vp_h, scale

    def _update_mouse(self, x, y):
        ratio = self.window.get_pixel_ratio()
        px = x * ratio
        py = y * ratio

        vp_x, vp_y, vp_w, vp_h, scale = self._get_screen_rect()
        if scale <= 0:
            return

        mx = int((px - vp_x) / scale)
        my = int(((vp_y + vp_h) - py) / scale)

        self.input.mouse_x = max(0, min(WIDTH - 1, mx))
        self.input.mouse_y = max(0, min(HEIGHT - 1, my))

    def load_game(self, filename=None):
        self.audio.stop_all()
        self.audio._sfx_cache.clear()

        if filename is not None:
            self.filename = filename

        try:
            cart = CartridgeParser.load(self.filename)
            self.memory.load_cartridge(cart)
            self.graphics.clip()
            self.graphics.cls(0)

            api = TICAPI(self).build()

            self.game = {
                "__name__": "__tic_cartridge__",
                "__file__": self.filename,
                "__builtins__": __builtins__,
            }
            self.game.update(api)

            compiled = compile(cart.code, self.filename, "exec")
            exec(compiled, self.game, self.game)

            if callable(self.game.get("BOOT")):
                self.game["BOOT"]()

            if not callable(self.game.get("TIC")):
                raise RuntimeError("El cartucho no define TIC().")

            self.error = None
            self.running = True
            self.paused = False
            print("[TICPY] Cartucho cargado:", self.filename)

        except Exception:
            self.game = None
            self.error = traceback.format_exc()
            print(self.error)

    def update(self, dt):
        if not self.running or self.paused:
            return

        if dt > 0.1:
            return

        self.input.update()
        self.audio.update()

        if self.game is None:
            return

        try:
            tic = self.game.get("TIC")
            if callable(tic):
                tic()

            ovr = self.game.get("OVR")
            if callable(ovr):
                ovr()

            bdr = self.game.get("BDR")
            if callable(bdr):
                for row in range(HEIGHT):
                    bdr(row)

            self.frame_count += 1
            self.input.reset_scroll()

        except Exception:
            self.error = traceback.format_exc()
            self.paused = True
            print(self.error)

    def _draw_game(self):
        fb_w, fb_h = self.window.get_framebuffer_size()
        fb_w, fb_h = max(1, fb_w), max(1, fb_h)

        gl.glViewport(0, 0, fb_w, fb_h)
        self.window.projection = pyglet.math.Mat4.orthogonal_projection(
            0, fb_w, 0, fb_h, -1, 1
        )

        vp_x, vp_y, vp_w, vp_h, _ = self._get_screen_rect()
        scn = self.game.get("SCN") if self.game else None

        self.graphics.update_texture(scn if callable(scn) else None)
        self.graphics.texture.blit(vp_x, vp_y, width=vp_w, height=vp_h)

    def stop(self):
        self.running = False
        pyglet.app.exit()

    def run(self):
        pyglet.app.run()

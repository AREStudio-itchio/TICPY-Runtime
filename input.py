import pyglet


class TICInput:

    BUTTONS = [
        (pyglet.window.key.UP, pyglet.window.key.W),
        (pyglet.window.key.DOWN, pyglet.window.key.S),
        (pyglet.window.key.LEFT, pyglet.window.key.A),
        (pyglet.window.key.RIGHT, pyglet.window.key.D),
        (pyglet.window.key.Z, pyglet.window.key.J),
        (pyglet.window.key.X, pyglet.window.key.K),
        (pyglet.window.key.C, pyglet.window.key.L),
        (pyglet.window.key.V, pyglet.window.key.I),
    ]

    def __init__(self):

        self.keys = set()
        self.key_timers = {}
        self.btn_timers = [0] * 32
        self.current = 0

        self.mouse_x = 0
        self.mouse_y = 0

        self.mouse_left = False
        self.mouse_middle = False
        self.mouse_right = False

        self.scroll_x = 0
        self.scroll_y = 0

        self.controllers = []
        self._init_controllers()

    def _init_controllers(self):
        try:
            self.manager = pyglet.input.ControllerManager()

            @self.manager.event
            def on_connect(controller):
                if len(self.controllers) < 4 and controller not in self.controllers:
                    controller.open()
                    self.controllers.append(controller)

            @self.manager.event
            def on_disconnect(controller):
                if controller in self.controllers:
                    self.controllers.remove(controller)

            for ctrl in self.manager.get_controllers()[:4]:
                ctrl.open()
                self.controllers.append(ctrl)
        except Exception:
            pass

    def key_down(self, symbol):
        if symbol not in self.keys:
            self.keys.add(symbol)
            self.key_timers[symbol] = 0

    def key_up(self, symbol):
        self.keys.discard(symbol)
        self.key_timers.pop(symbol, None)

    def update(self):
        self.current = 0

        for index, mapping in enumerate(self.BUTTONS):
            if self.keys.intersection(mapping):
                self.current |= 1 << index

        for p_idx, ctrl in enumerate(self.controllers):
            offset = p_idx * 8
            if ctrl.dpad_up or ctrl.lefty > 0.5:
                self.current |= 1 << (offset + 0)
            if ctrl.dpad_down or ctrl.lefty < -0.5:
                self.current |= 1 << (offset + 1)
            if ctrl.dpad_left or ctrl.leftx < -0.5:
                self.current |= 1 << (offset + 2)
            if ctrl.dpad_right or ctrl.leftx > 0.5:
                self.current |= 1 << (offset + 3)
            if ctrl.a:
                self.current |= 1 << (offset + 4)
            if ctrl.b:
                self.current |= 1 << (offset + 5)
            if ctrl.x:
                self.current |= 1 << (offset + 6)
            if ctrl.y:
                self.current |= 1 << (offset + 7)

        for i in range(32):
            if self.current & (1 << i):
                self.btn_timers[i] += 1
            else:
                self.btn_timers[i] = 0

        for sym in list(self.keys):
            self.key_timers[sym] = self.key_timers.get(sym, 0) + 1

    def reset_scroll(self):
        self.scroll_x = 0
        self.scroll_y = 0

    def btn(self, index=-1):
        if index < 0:
            return self.current

        if index > 31:
            return False

        return bool(self.current & (1 << index))

    def btnp(self, index=-1, hold=-1, period=-1):
        hold = int(hold)
        period = int(period)

        def is_pressed(idx):
            t = self.btn_timers[idx]
            if t == 1:
                return True
            if hold >= 0 and period > 0 and t > hold:
                return (t - hold) % period == 0
            return False

        if index < 0:
            mask = 0
            for i in range(32):
                if is_pressed(i):
                    mask |= 1 << i
            return mask

        if index > 31:
            return False

        return is_pressed(int(index))

    def key(self, symbol=None):
        if symbol is None:
            return bool(self.keys)

        return symbol in self.keys

    def keyp(self, symbol=None, hold=-1, period=-1):
        hold = int(hold)
        period = int(period)

        def check_sym(sym):
            t = self.key_timers.get(sym, 0)
            if t == 1:
                return True
            if hold >= 0 and period > 0 and t > hold:
                return (t - hold) % period == 0
            return False

        if symbol is None:
            return any(check_sym(s) for s in self.keys)

        return check_sym(symbol)

    def mouse(self):
        return (
            self.mouse_x,
            self.mouse_y,
            self.mouse_left,
            self.mouse_middle,
            self.mouse_right,
            self.scroll_x,
            self.scroll_y,
        )

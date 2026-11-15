import time


class TICAPI:

    def __init__(self, runtime):
        self.runtime = runtime

    def build(self):
        r = self.runtime
        g = r.graphics
        m = r.memory
        i = r.input
        a = r.audio

        return {
            # Graphics
            "cls": g.cls,
            "pix": g.pix,
            "line": g.line,
            "rect": g.rect,
            "rectb": g.rectb,
            "circ": g.circ,
            "circb": g.circb,
            "ellip": g.ellip,
            "ellipb": g.ellipb,
            "tri": g.tri,
            "trib": g.trib,
            "ttri": g.ttri,
            "vbank": g.vbank,
            "spr": g.spr,
            "map": g.map,
            "print": g.print_text,
            "font": g.font,
            "clip": g.clip,
            "reset": r.load_game,


            # Input
            "btn": i.btn,
            "btnp": i.btnp,
            "key": i.key,
            "keyp": i.keyp,
            "mouse": i.mouse,

            # Memory
            "peek": m.peek,
            "poke": m.poke,
            "peek1": m.peek1,
            "poke1": m.poke1,
            "peek2": m.peek2,
            "poke2": m.poke2,
            "peek4": m.peek4,
            "poke4": m.poke4,
            "memcpy": m.memcpy,
            "memset": m.memset,
            "pmem": m.pmem,
            "sync": m.sync,

            # Map
            "mget": m.mget,
            "mset": m.mset,

            # Flags
            "fget": m.fget,
            "fset": m.fset,

            # Audio
            "sfx": a.sfx,
            "music": a.music,

            # System
            "time": lambda: int(time.monotonic() * 1000),
            "tstamp": lambda: int(time.time()),
            "trace": self.trace,
            "exit": r.stop,
        }

    def trace(self, message, color=15):
        print(f"[TIC80] {message}")

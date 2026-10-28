"""Exercise production detach/destructor ordering without game assets."""
from pathlib import Path
import subprocess, tempfile
source = Path("upstream/gumps/Gump_manager.cc").read_text()
start = source.index("bool Gump_manager::remove_gump(Gump* gump) {")
brace = source.index("{", start)
depth = 0
for end in range(brace, len(source)):
    if source[end] == "{": depth += 1
    elif source[end] == "}":
        depth -= 1
        if not depth: break
method = source[start:end+1]
harness = r"""
#include <cassert>
#include <cstddef>
struct Queue { void resume(int) {} };
struct Window { Queue queue; Queue* get_tqueue() { return &queue; } } window;
Window* gwin = &window;
namespace Game { int get_ticks() { return 0; } }
struct Gump {
    int layer = -1, layer2 = -1, releases = 0;
    bool persistent = false;
    void free_render_layer() {
        if (layer >= 0) ++releases;
        if (layer2 >= 0) ++releases;
        layer = layer2 = -1;
    }
    bool is_persistent() { return persistent; }
};
struct Gump_list {
    Gump* gump; Gump_list* next;
};
struct Gump_manager {
    Gump* kbd_focus = nullptr;
    Gump_list* open_gumps = nullptr;
    int non_persistent_count = 0;
    bool dont_pause_game = false;
    void set_kbd_focus(Gump* p) { kbd_focus = p; }
    bool remove_gump(Gump*);
};
"""
harness += method
harness += r"""
int main() {
    Gump_manager manager;
    Gump selector, actions;
    selector.layer = 10; selector.layer2 = 11;
    manager.open_gumps = new Gump_list{&selector, nullptr};
    manager.non_persistent_count = 1;
    manager.kbd_focus = &selector;
    manager.remove_gump(&selector);
    // Selector still exists while its derived destructor opens action menu.
    assert(selector.layer == -1 && selector.layer2 == -1);
    assert(selector.releases == 2 && manager.kbd_focus == nullptr);
    actions.layer = 12;
    manager.open_gumps = new Gump_list{&actions, nullptr};
    manager.non_persistent_count = 1;
    manager.remove_gump(&actions);
    // Action menu still exists throughout blocking object activation/dialogue.
    assert(actions.layer == -1 && selector.layer == -1);
    assert(manager.open_gumps == nullptr);
    assert(manager.non_persistent_count == 0);
    actions.free_render_layer(); selector.free_render_layer();
    assert(actions.releases == 1 && selector.releases == 2);
    // Removing/readding a nonmodal gump for z-order may recreate its layer.
    Gump first, last;
    first.layer = 20; last.layer = 21;
    manager.open_gumps = new Gump_list{&first, new Gump_list{&last, nullptr}};
    manager.non_persistent_count = 2;
    manager.remove_gump(&last);
    assert(last.layer == -1 && first.layer == 20);
    last.layer = 22;
    manager.remove_gump(&first);
    last.free_render_layer();
    assert(last.releases == 2);
}
"""
with tempfile.TemporaryDirectory() as folder:
    cpp = Path(folder) / "menu.cpp"
    binary = Path(folder) / "menu"
    cpp.write_text(harness)
    subprocess.run(["clang++", "-std=c++17", "-fsanitize=address,undefined",
                    str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: selector -> action menu -> conversation; two layers; idempotent cleanup; reorder")

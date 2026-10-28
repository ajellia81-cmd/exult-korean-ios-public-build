"""Exercise the production iOS lifecycle watch/poll with engine stand-ins."""
import pathlib,subprocess,tempfile
s=pathlib.Path("upstream/exult.cc").read_text()
a=s.index("#ifdef SDL_PLATFORM_IOS\nstatic std::atomic<bool> exult_ios_background")
b=s.index("static void Init()",a)
production=s[a:b]
prefix=r'''
#include <atomic>
#include <cassert>
#include <iostream>
#define SDL_PLATFORM_IOS 1
#define SDLCALL
enum{SDL_EVENT_WILL_ENTER_BACKGROUND=1,SDL_EVENT_DID_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_FOREGROUND,SDL_EVENT_WILL_ENTER_FOREGROUND};
struct SDL_Event{int type;};
bool main_thread=true;
bool SDL_IsMainThread(){return main_thread;}
struct MockWindow{
 bool focus=true,actor=true;int lost=0,gained=0,pause_depth=0;
 bool have_focus(){return focus;}
 void* get_main_actor(){return actor?this:nullptr;}
 void lose_focus(){if(!focus)return;focus=false;++lost;++pause_depth;}
 void get_focus(){if(focus)return;focus=true;++gained;--pause_depth;}
};
MockWindow window;MockWindow* gwin=&window;
struct Audio{
 bool paused=false;int pauses=0,resumes=0;
 static Audio* get_ptr(){static Audio a;return &a;}
 void pause_audio(){paused=true;++pauses;}
 void resume_audio(){paused=false;++resumes;}
};
int pumps=0;
void SDL_PumpEvents();
void SDL_Delay(int){}
'''
tests=r'''
void send(int type){SDL_Event e{type};exult_ios_lifecycle_watch(nullptr,&e);}
void SDL_PumpEvents(){
 ++pumps;
 assert(!window.focus && window.pause_depth>0 && Audio::get_ptr()->paused);
 if(pumps==3)send(SDL_EVENT_DID_ENTER_FOREGROUND);
}
int main(){
 send(SDL_EVENT_WILL_ENTER_BACKGROUND);
 assert(!window.focus&&window.lost==1&&Audio::get_ptr()->paused);
 send(SDL_EVENT_DID_ENTER_BACKGROUND);assert(window.lost==1);
 send(SDL_EVENT_WILL_ENTER_FOREGROUND);assert(!window.focus);
 exult_ios_lifecycle_poll();
 assert(pumps==3&&window.focus&&window.pause_depth==0);
 assert(window.gained==1&&!Audio::get_ptr()->paused);
 send(SDL_EVENT_DID_ENTER_FOREGROUND);assert(window.gained==1);
 // A pre-existing pause/focus loss must remain paused on return.
 window.focus=false;window.pause_depth=2;Audio::get_ptr()->paused=true;
 send(SDL_EVENT_WILL_ENTER_BACKGROUND);send(SDL_EVENT_DID_ENTER_FOREGROUND);
 assert(!window.focus&&window.pause_depth==2&&Audio::get_ptr()->paused);
 // Native event from another thread only changes the atomic request.
 window.focus=true;window.pause_depth=0;main_thread=false;
 send(SDL_EVENT_WILL_ENTER_BACKGROUND);assert(window.focus);
 main_thread=true;exult_ios_apply_lifecycle();assert(!window.focus);
 send(SDL_EVENT_DID_ENTER_FOREGROUND);assert(window.focus&&window.pause_depth==0);
 // Menu without an actor still pauses/resumes audio without writing a game.
 window.actor=false;
 const int prior_lost=window.lost;
 send(SDL_EVENT_WILL_ENTER_BACKGROUND);
 assert(window.lost==prior_lost&&Audio::get_ptr()->paused);
 send(SDL_EVENT_DID_ENTER_FOREGROUND);assert(!Audio::get_ptr()->paused);
 std::cout<<"PASS: native background watch, suspended loop, duplicate events, prior pause, thread handoff and menu audio\n";
}
'''
with tempfile.TemporaryDirectory() as d:
    cpp=pathlib.Path(d)/"lifecycle.cc";exe=pathlib.Path(d)/"lifecycle"
    cpp.write_text(prefix+production+tests)
    subprocess.run(["clang++","-std=c++17","-fsanitize=address,undefined",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
# Verify both ordinary gameplay and secondary event loops guard focus gain.
assert s.count("if (exult_ios_background.load()) break;")==2
assert "exult_ios_lifecycle_poll();" in pathlib.Path("upstream/gumps/gump_utils.h").read_text()
assert "if (focus) return;" in pathlib.Path("upstream/gamewin.cc").read_text()

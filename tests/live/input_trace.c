/* Minimal test core: log actual RetroPad reads without graphics or ROM data. */
#include "libretro.h"
#include <stdio.h>
#include <unistd.h>
static retro_environment_t env;
static retro_video_refresh_t video;
static retro_input_poll_t poll;
static retro_input_state_t input;
static unsigned frames;
static unsigned last[2] = {65535,65535};
void retro_set_environment(retro_environment_t cb) { env=cb; bool yes=true; env(RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME,&yes); }
void retro_set_video_refresh(retro_video_refresh_t cb) { video=cb; }
void retro_set_audio_sample(retro_audio_sample_t cb) { (void)cb; }
void retro_set_audio_sample_batch(retro_audio_sample_batch_t cb) { (void)cb; }
void retro_set_input_poll(retro_input_poll_t cb) { poll=cb; }
void retro_set_input_state(retro_input_state_t cb) { input=cb; }
void retro_init(void) {}
void retro_deinit(void) {}
unsigned retro_api_version(void) {return RETRO_API_VERSION;}
void retro_get_system_info(struct retro_system_info *i) { *i=(struct retro_system_info){.library_name="Router Input Trace",.library_version="1",.valid_extensions="",.need_fullpath=false}; }
void retro_get_system_av_info(struct retro_system_av_info *i) { *i=(struct retro_system_av_info){.geometry={320,240,320,240,4.0/3.0},.timing={60,44100}}; }
void retro_set_controller_port_device(unsigned p,unsigned d) { (void)p;(void)d; }
void retro_reset(void) {}
void retro_run(void) {
 poll();
 for(unsigned p=0;p<2;p++) {unsigned bits=0;for(unsigned b=0;b<16;b++) if(input(p,RETRO_DEVICE_JOYPAD,0,b)) bits|=1u<<b;
 if(bits!=last[p]) {fprintf(stderr,"ROUTER_TRACE frame=%u player=%u mask=%u\n",frames,p+1,bits);fflush(stderr);last[p]=bits;}}
 video(NULL,320,240,0); frames++; usleep(16000);
 if(frames>=1200) env(RETRO_ENVIRONMENT_SHUTDOWN,NULL);
}
bool retro_load_game(const struct retro_game_info *g) {(void)g;return true;}
bool retro_load_game_special(unsigned t,const struct retro_game_info *g,size_t n) {(void)t;(void)g;(void)n;return false;}
void retro_unload_game(void) {}
unsigned retro_get_region(void) {return RETRO_REGION_NTSC;}
void *retro_get_memory_data(unsigned id) {(void)id;return NULL;}
size_t retro_get_memory_size(unsigned id) {(void)id;return 0;}
size_t retro_serialize_size(void) {return 0;}
bool retro_serialize(void *data,size_t size) {(void)data;(void)size;return false;}
bool retro_unserialize(const void *data,size_t size) {(void)data;(void)size;return false;}
void retro_cheat_reset(void) {}
void retro_cheat_set(unsigned i,bool e,const char*c) {(void)i;(void)e;(void)c;}

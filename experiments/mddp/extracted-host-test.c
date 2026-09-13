#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#include <errno.h>
typedef uint32_t u32;
#define READ_ONCE(x) (x)
#define MDDP_FEATURE_MDDP_WH 4
#define MDDP_APP_TYPE_WH 1
#define MDDP_APP_TYPE_ALL 255
#define MDDP_MOD_CNT 1
#define MDDP_S_LOG(...) ((void)0)

enum mddp_state_e {
	MDDP_STATE_UNINIT = 0,
	MDDP_STATE_ENABLING,
	MDDP_STATE_DEACTIVATED,
	MDDP_STATE_ACTIVATING,
	MDDP_STATE_ACTIVATED,
	MDDP_STATE_DEACTIVATING,
	MDDP_STATE_DISABLING,
	MDDP_STATE_DISABLED,

	MDDP_STATE_CNT,
	MDDP_STATE_DUMMY = 0x7fff /* Make it a 2-byte enum. */
};

enum mddp_event_e {
	MDDP_EVT_FUNC_ENABLE,  /**< Enable MDDP. */
	MDDP_EVT_FUNC_DISABLE,  /**< Disable MDDP. */
	MDDP_EVT_FUNC_ACT,  /**< Activate MDDP. */
	MDDP_EVT_FUNC_DEACT,  /**< Deactivate MDDP. */

	MDDP_EVT_MD_RSP_OK,  /**< MD Response OK. */
	MDDP_EVT_MD_RSP_TIMEOUT,  /**<MD Response timeout. */

	MDDP_EVT_MD_RESET,  /**<MD send RESET. */

	MDDP_EVT_MD_RSP_FAIL,  /* Append: preserve existing event numbers. */

	MDDP_EVT_CNT,
	MDDP_EVT_DUMMY = 0x7fff  /* Make it a 2-byte enum */
};


enum mddp_app_type_e { APP_DUMMY };
enum { MDDP_CMCMD_ENABLE_RSP, MDDP_CMCMD_ACT_RSP, MDDP_CMCMD_DISABLE_RSP, MDDP_CMCMD_DEACT_RSP };
struct mddp_dev_rsp_enable_t { int unused; };
struct mddp_dev_rsp_act_t { int unused; };
struct mddp_dev_rsp_disable_t { int unused; };
struct mddp_dev_rsp_deact_t { int unused; };
struct mddp_app_t {
 int type; enum mddp_state_e state; u32 feature, drv_reg;
 int md_resp_comp;
 struct { void (*change_state)(int, void*, void*); } drv_hdlr;
};
struct mddp_sm_entry_t { enum mddp_event_e event; enum mddp_state_e new_state; void (*action)(struct mddp_app_t*); };
static bool legacy_wh_handshake;
static int mddp_state_handler_mtx;
static void mutex_lock(int *p) { assert(*p==0); *p=1; }
static void mutex_unlock(int *p) { assert(*p==1); *p=0; }
static struct mddp_app_t app;
static int hook, unhook, calls, success, completed_state, emitted_enable;
static int mddp_hook_work, mddp_unhook_work;
static const unsigned mddp_sm_module_list_s[] = {MDDP_APP_TYPE_WH};
static void schedule_work(int *work) { if (work == &mddp_hook_work) hook++; else unhook++; }
static void mddp_dev_response(int t, int cmd, bool ok, uint8_t *p, unsigned n) { (void)t; (void)cmd; (void)p; (void)n; calls++; success=ok; }
static enum mddp_state_e mddp_get_state(struct mddp_app_t *a) { return a->state; }
static void complete(int *p) { (*p)++; completed_state=app.state; }
static struct mddp_app_t *mddp_get_app_inst(unsigned t) { (void)t; return &app; }
static void mddp_sm_wait_pre(struct mddp_app_t *a) { a->md_resp_comp=0; }
static void mddp_sm_wait(struct mddp_app_t *a, int e) { (void)a; (void)e; }
static void mddpwh_sm_md_reset(struct mddp_app_t *a) { a->feature=2; }
static void mddpwh_sm_deact(struct mddp_app_t *a) { (void)a; }
static enum mddp_state_e mddp_sm_on_event_locked(struct mddp_app_t*, enum mddp_event_e);

bool mddp_legacy_wh_handshake(struct mddp_app_t *app)
{
	u32 feature = READ_ONCE(app->feature);

	return legacy_wh_handshake && app->type == MDDP_APP_TYPE_WH &&
		(feature & ~MDDP_FEATURE_MDDP_WH) == 0x3;
}

static void mddpwh_sm_rsp_enable_ok(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_enable_t            enable = {0};

	/* Only reached from an accepted ENABLE success response. */
	if (mddp_legacy_wh_handshake(app))
		app->feature |= MDDP_FEATURE_MDDP_WH;

	// 1. Send RSP to WiFi
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);

	// 2. Send RSP to upper module.
	mddp_dev_response(app->type, MDDP_CMCMD_ENABLE_RSP,
			true, (uint8_t *)&enable, sizeof(enable));
}

static void mddpwh_sm_rsp_enable_fail(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_enable_t    enable = {0};

	// 1. Send RSP to WiFi
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);

	// 2. Send RSP to upper module.
	mddp_dev_response(app->type, MDDP_CMCMD_ENABLE_RSP,
			false, (uint8_t *)&enable, sizeof(enable));
}

static void mddpwh_sm_rsp_act_ok(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_act_t       act = {0};

	// 1. Send RSP to WiFi
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);

	// 2. Send RSP to upper module.
	mddp_dev_response(app->type, MDDP_CMCMD_ACT_RSP,
			true, (uint8_t *)&act, sizeof(act));

	schedule_work(&mddp_hook_work);
}

static void mddpwh_sm_rsp_act_fail(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_act_t rsp = {0};

	schedule_work(&mddp_unhook_work);
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);
	mddp_dev_response(app->type, MDDP_CMCMD_ACT_RSP,
			false, (uint8_t *)&rsp, sizeof(rsp));
}

static void mddpwh_sm_rsp_disable(struct mddp_app_t *app)
{
	// 1. Send RSP to WiFi
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);

	// 2. NO NEED to send RSP to upper module.

}

static void mddpwh_sm_rsp_disable_fail(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_disable_t rsp = {0};

	schedule_work(&mddp_unhook_work);
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);
	mddp_dev_response(app->type, MDDP_CMCMD_DISABLE_RSP,
			false, (uint8_t *)&rsp, sizeof(rsp));
}

static void mddpwh_sm_rsp_deact(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_deact_t     deact = {0};

	schedule_work(&mddp_unhook_work);

	// 2. Send RSP to WiFi
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);

	// 3. Send RSP to upper module.
	mddp_dev_response(app->type, MDDP_CMCMD_DEACT_RSP,
			true, (uint8_t *)&deact, sizeof(deact));
}

static void mddpwh_sm_rsp_deact_fail(struct mddp_app_t *app)
{
	struct mddp_dev_rsp_deact_t rsp = {0};

	schedule_work(&mddp_unhook_work);
	if (app->drv_hdlr.change_state != NULL)
		app->drv_hdlr.change_state(app->state, NULL, NULL);
	mddp_dev_response(app->type, MDDP_CMCMD_DEACT_RSP,
			false, (uint8_t *)&rsp, sizeof(rsp));
}

static struct mddp_sm_entry_t mddpwh_enabling_state_machine_s[] = {
/* event                  new_state                action */
{MDDP_EVT_MD_RESET,       MDDP_STATE_DISABLED,     mddpwh_sm_md_reset},
{MDDP_EVT_MD_RSP_OK,      MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_enable_ok},
{MDDP_EVT_MD_RSP_FAIL,    MDDP_STATE_DISABLED,     mddpwh_sm_rsp_enable_fail},
{MDDP_EVT_MD_RSP_TIMEOUT, MDDP_STATE_DISABLED,     mddpwh_sm_rsp_enable_fail},
{MDDP_EVT_DUMMY,          MDDP_STATE_ENABLING,     NULL} /* End of SM. */
};

static struct mddp_sm_entry_t mddpwh_activating_state_machine_s[] = {
/* event                  new_state                action */
{MDDP_EVT_MD_RESET,       MDDP_STATE_DEACTIVATED,  mddpwh_sm_md_reset},
{MDDP_EVT_FUNC_DEACT,     MDDP_STATE_DEACTIVATING, mddpwh_sm_deact},
{MDDP_EVT_MD_RSP_OK,      MDDP_STATE_ACTIVATED,    mddpwh_sm_rsp_act_ok},
{MDDP_EVT_MD_RSP_FAIL,    MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_act_fail},
{MDDP_EVT_MD_RSP_TIMEOUT, MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_act_fail},
{MDDP_EVT_DUMMY,          MDDP_STATE_ACTIVATING,   NULL} /* End of SM. */
};

static struct mddp_sm_entry_t mddpwh_disabling_state_machine_s[] = {
/* event                  new_state                action */
{MDDP_EVT_MD_RESET,       MDDP_STATE_DISABLED,     mddpwh_sm_md_reset},
{MDDP_EVT_MD_RSP_OK,      MDDP_STATE_DISABLED,     mddpwh_sm_rsp_disable},
{MDDP_EVT_MD_RSP_FAIL,    MDDP_STATE_DISABLED,     mddpwh_sm_rsp_disable_fail},
{MDDP_EVT_MD_RSP_TIMEOUT, MDDP_STATE_DISABLED,     mddpwh_sm_rsp_disable_fail},
{MDDP_EVT_DUMMY,          MDDP_STATE_DISABLING,    NULL} /* End of SM. */
};

static struct mddp_sm_entry_t mddpwh_deactivating_state_machine_s[] = {
/* event                  new_state                action */
{MDDP_EVT_MD_RESET,       MDDP_STATE_DEACTIVATED,  mddpwh_sm_md_reset},
{MDDP_EVT_MD_RSP_OK,      MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_deact},
{MDDP_EVT_MD_RSP_FAIL,    MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_deact_fail},
{MDDP_EVT_MD_RSP_TIMEOUT, MDDP_STATE_DEACTIVATED,  mddpwh_sm_rsp_deact_fail},
{MDDP_EVT_DUMMY,          MDDP_STATE_DEACTIVATING, NULL} /* End of SM. */
};


static enum mddp_state_e mddp_sm_on_event_locked(struct mddp_app_t *a, enum mddp_event_e e) {
 struct mddp_sm_entry_t *s=NULL;
 assert(mddp_state_handler_mtx==1);
 if (e == MDDP_EVT_FUNC_ENABLE) { emitted_enable++; a->state=MDDP_STATE_ENABLING; return a->state; }
 switch (a->state) {
 case MDDP_STATE_ENABLING: s=mddpwh_enabling_state_machine_s; break;
 case MDDP_STATE_ACTIVATING: s=mddpwh_activating_state_machine_s; break;
 case MDDP_STATE_DISABLING: s=mddpwh_disabling_state_machine_s; break;
 case MDDP_STATE_DEACTIVATING: s=mddpwh_deactivating_state_machine_s; break;
 default: return MDDP_STATE_DUMMY;
 }
 for (;s->event != MDDP_EVT_DUMMY;s++) if(s->event==e) {
  a->state=s->new_state; if(s->action) s->action(a); return a->state;
 }
 return MDDP_STATE_DUMMY;
}

enum mddp_state_e mddp_sm_on_event(struct mddp_app_t *app,
	enum mddp_event_e event)
{
	enum mddp_state_e state;

	mutex_lock(&mddp_state_handler_mtx);
	state = mddp_sm_on_event_locked(app, event);
	mutex_unlock(&mddp_state_handler_mtx);
	return state;
}

enum mddp_state_e mddp_sm_set_state_by_md_rsp(struct mddp_app_t *app,
	enum mddp_state_e prev_state,
	bool md_rsp_result)
{
	enum mddp_state_e       curr_state;
	enum mddp_state_e       new_state = MDDP_STATE_DUMMY;
	enum mddp_event_e       event;

	mutex_lock(&mddp_state_handler_mtx);
	curr_state = mddp_get_state(app);
	event = md_rsp_result ? MDDP_EVT_MD_RSP_OK : MDDP_EVT_MD_RSP_FAIL;

	if (curr_state == prev_state) {
		/* OK.
		 * There is no interrupt event from upper module
		 * when MD handles this request.
		 */
		new_state = mddp_sm_on_event_locked(app, event);
		complete(&app->md_resp_comp);

		MDDP_S_LOG(MDDP_LL_NOTICE,
				"%s: OK. event(%d), prev_state(%d) -> new_state(%d).\n",
				__func__, event, prev_state, new_state);

		mutex_unlock(&mddp_state_handler_mtx);
		return new_state;
	}

	mutex_unlock(&mddp_state_handler_mtx);

	/* DC (Don't Care).
	 * There are interrupt events from upper module
	 * when MD handles this request.
	 */
	MDDP_S_LOG(MDDP_LL_WARN,
			"%s: DC. event(%d), prev_state(%d) -> new_state(%d).\n",
			__func__, event, prev_state, new_state);

	return MDDP_STATE_DUMMY;
}

int32_t mddp_on_enable(enum mddp_app_type_e in_type)
{
	struct mddp_app_t      *app;
	uint32_t                type;
	uint8_t                 idx;

	if (in_type != MDDP_APP_TYPE_ALL)
		return -EINVAL;

	/*
	 * MDDP ENABLE command.
	 */
	for (idx = 0; idx < MDDP_MOD_CNT; idx++) {
		type = mddp_sm_module_list_s[idx];
		app = mddp_get_app_inst(type);
		if (!app->drv_reg ||
		    (!(app->feature & MDDP_FEATURE_MDDP_WH) &&
		     !mddp_legacy_wh_handshake(app)))
			continue;
		mddp_sm_wait_pre(app);
		mddp_sm_on_event(app, MDDP_EVT_FUNC_ENABLE);
		mddp_sm_wait(app, MDDP_EVT_FUNC_ENABLE);
	}

	return 0;
}


static void reset(enum mddp_state_e state, unsigned feature) {
 app=(struct mddp_app_t){.type=MDDP_APP_TYPE_WH,.state=state,.feature=feature,.drv_reg=1};
 hook=unhook=calls=success=emitted_enable=0; completed_state=-1;
}
int main(void) {
 unsigned cases=0;
 for(unsigned feat=0;feat<16;feat++) for(int opt=0;opt<2;opt++) {
  reset(MDDP_STATE_DISABLED,feat); legacy_wh_handshake=opt;
  mddp_on_enable(MDDP_APP_TYPE_ALL);
  assert(emitted_enable == (!!(feat&4) || (opt && feat==3)));
  assert(app.feature==feat); cases++;
 }
 reset(MDDP_STATE_DISABLED,3); legacy_wh_handshake=true; app.drv_reg=0;
 mddp_on_enable(MDDP_APP_TYPE_ALL); assert(!emitted_enable); cases++;
 reset(MDDP_STATE_DISABLED,0x40000003); mddp_on_enable(MDDP_APP_TYPE_ALL);
 assert(!emitted_enable); cases++;
 for(int result=0;result<2;result++) {
  reset(MDDP_STATE_ENABLING,3);
  mddp_sm_set_state_by_md_rsp(&app,MDDP_STATE_ENABLING,result);
  assert(app.feature == (result?7:3)); assert(calls==1 && success==result);
  assert(app.state == (result?MDDP_STATE_DEACTIVATED:MDDP_STATE_DISABLED));
  assert(app.md_resp_comp==1 && completed_state==(int)app.state); cases++;
 }
 reset(MDDP_STATE_ENABLING,3);
 mddp_sm_on_event(&app,MDDP_EVT_MD_RSP_TIMEOUT);
 assert(app.feature==3 && app.state==MDDP_STATE_DISABLED && calls==1 && !success); cases++;
 for(int result=0;result<2;result++) {
  reset(MDDP_STATE_ACTIVATING,7);
  mddp_sm_set_state_by_md_rsp(&app,MDDP_STATE_ACTIVATING,result);
  assert(app.state==(result?MDDP_STATE_ACTIVATED:MDDP_STATE_DEACTIVATED));
  assert(success==result && calls==1 && hook==result); cases++;
 }
 reset(MDDP_STATE_ACTIVATING,7); mddp_sm_on_event(&app,MDDP_EVT_MD_RSP_TIMEOUT);
 assert(app.state==MDDP_STATE_DEACTIVATED && !hook && calls==1 && !success); cases++;
 for(int phase=0;phase<2;phase++) for(int timedout=0;timedout<2;timedout++) {
  reset(phase?MDDP_STATE_DISABLING:MDDP_STATE_DEACTIVATING,7);
  if(timedout) mddp_sm_on_event(&app,MDDP_EVT_MD_RSP_TIMEOUT);
  else mddp_sm_set_state_by_md_rsp(&app,app.state,false);
  assert(calls==1 && !success && !hook && unhook==1); cases++;
 }
 reset(MDDP_STATE_DISABLED,3);
 mddp_sm_set_state_by_md_rsp(&app,MDDP_STATE_ENABLING,true);
 assert(!calls && app.feature==3 && app.md_resp_comp==0); cases++;
 assert(mddp_state_handler_mtx==0);
 assert(MDDP_EVT_MD_RESET==6 && MDDP_EVT_MD_RSP_FAIL==7);
 printf("PASS: %u extracted-C scenarios; no kernel/IPC/hardware acceptance claimed\n",cases);
}

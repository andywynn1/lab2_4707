/* Test shims for the real functions inserted by run_unit.py. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>

typedef uint64_t uint64;
typedef uint32_t uint32;
typedef size_t Size;
typedef int Buffer;
typedef void *BufferAccessStrategy;
typedef struct { int buf_id; uint64 last_access; uint32 state; } BufferDesc;
typedef struct { int refcount; } PrivateRefCountEntry;
typedef struct { char *data; size_t len; } StringInfoData;
#define UINT64_FORMAT "%" PRIu64
#define BM_LOCKED (1U << 31)
#define BM_VALID (1U << 30)
#define BUF_REFCOUNT_ONE 1
#define BUF_USAGECOUNT_ONE (1U << 16)
#define BM_MAX_USAGE_COUNT 5
#define BUF_STATE_GET_REFCOUNT(s) ((s) & 0xffff)
#define BUF_STATE_GET_USAGECOUNT(s) (((s) >> 16) & 7)
#define Assert assert
#define INT_ACCESS_ONCE(x) (x)
#define LOG 1
#define ERROR 2
#define BufferDescriptorGetBuffer(b) ((b)->buf_id + 1)
#define BufferIsLocal(b) ((b) < 0)
#define VALGRIND_MAKE_MEM_DEFINED(p, n) ((void) 0)
#define BLCKSZ 8192

static BufferDesc buffers[16];
static PrivateRefCountEntry refs[16];
static int NBuffers, locks, allocations, lock_calls, inject_mode, steps;
static uint64 clock_value;
static char log_text[8192];
static jmp_buf error_target;
static struct { int bgwprocno; uint32 numBufferAllocs; } control;
#define StrategyControl (&control)
static struct { int procLatch; } procs[1];
static struct { void *allProcs; } unused;
static struct { typeof(procs[0]) *allProcs; } proc_global = {procs};
#define ProcGlobal (&proc_global)
#define CurrentResourceOwner NULL
#define CHECK_FOR_INTERRUPTS() assert(++steps < 10000)

static BufferDesc *GetBufferDescriptor(int id) { assert(id >= 0 && id < NBuffers); return &buffers[id]; }
static uint32 LockBufHdr(BufferDesc *buf)
{
	assert(locks == 0);
	if (++lock_calls == NBuffers + 1 && inject_mode)
	{
		if (inject_mode == 1) buf->state += BUF_REFCOUNT_ONE;
		else if (inject_mode == 2) { buf->last_access = 99; clock_value = 100; }
		else { buffers[0].last_access = 99; clock_value = 100; }
		inject_mode = 0;
	}
	assert(!(buf->state & BM_LOCKED));
	locks++;
	return buf->state |= BM_LOCKED;
}
static void UnlockBufHdr(BufferDesc *buf, uint32 state)
{
	assert(locks == 1 && (buf->state & BM_LOCKED));
	buf->state = state & ~BM_LOCKED;
	locks--;
}
static uint64 StrategyNextTimestamp(void) { assert(locks == 1); return clock_value++; }
static uint64 StrategyCurrentTimestamp(void) { return clock_value; }
static uint32 pg_atomic_read_u32(uint32 *p) { return *p; }
static uint32 pg_atomic_fetch_add_u32(uint32 *p, uint32 n) { uint32 old = *p; *p += n; return old; }
static bool pg_atomic_compare_exchange_u32(uint32 *p, uint32 *expected, uint32 value)
{
	if (*p != *expected) { *expected = *p; return false; }
	*p = value;
	return true;
}
static uint32 WaitBufHdrUnlocked(BufferDesc *buf) { assert(!(buf->state & BM_LOCKED)); return buf->state; }
static void SetLatch(int *latch) { *latch = 1; }
static void *palloc(size_t size) { void *p; assert(!locks); p = malloc(size); assert(p); allocations++; return p; }
static void pfree(void *p) { assert(!locks && p); free(p); allocations--; }
static void initStringInfo(StringInfoData *s) { s->data = palloc(8192); s->len = 0; s->data[0] = 0; }
static void appendStringInfo(StringInfoData *s, const char *fmt, ...)
{
	int count; va_list ap; assert(!locks); va_start(ap, fmt);
	count = vsnprintf(s->data + s->len, 8192 - s->len, fmt, ap); va_end(ap);
	assert(count >= 0 && (size_t) count < 8192 - s->len); s->len += count;
}
static void elog(int level, const char *fmt, ...)
{
	va_list ap; assert(!locks); va_start(ap, fmt);
	vsnprintf(log_text, sizeof(log_text), fmt, ap); va_end(ap);
	if (level == ERROR) longjmp(error_target, 1);
}
static PrivateRefCountEntry *GetPrivateRefCountEntry(Buffer b, bool move)
{ return refs[b - 1].refcount ? &refs[b - 1] : NULL; }
static void ReservePrivateRefCountEntry(void) { assert(!locks); }
static PrivateRefCountEntry *NewPrivateRefCountEntry(Buffer b) { return &refs[b - 1]; }
static void ResourceOwnerRememberBuffer(void *owner, Buffer b) { assert(!locks); }

/* PRODUCTION_CODE */

static void reset(int n)
{
	assert(!locks && !allocations);
	memset(buffers, 0, sizeof(buffers)); memset(refs, 0, sizeof(refs));
	NBuffers = n; clock_value = 1; lock_calls = 0; inject_mode = 0; steps = 0;
	control.bgwprocno = -1; control.numBufferAllocs = 0;
	for (int i = 0; i < n; i++) buffers[i].buf_id = i;
}
static int select_id(void)
{
	uint32 state; bool from_ring = true; BufferSelectionSnapshot snapshot;
	BufferDesc *buf = StrategyGetBuffer(NULL, &state, &from_ring, &snapshot);
	int id = buf->buf_id;
	assert(!from_ring && locks == 1 && (state & BM_LOCKED));
	assert(BUF_STATE_GET_REFCOUNT(state) == 0);
	assert(snapshot.candidates[snapshot.victim_index].last_access == buf->last_access);
	UnlockBufHdr(buf, state);
	StrategyLogSelection(&snapshot, 123);
	assert(strstr(log_text, "Candidate buffers:") && strstr(log_text, "Available Page Space: 123"));
	pfree(snapshot.candidates);
	assert(!allocations);
	return id;
}
int main(void)
{
	reset(3);
	buffers[0].last_access = 1; buffers[1].last_access = 4; buffers[2].last_access = 3; clock_value = 5;
	assert(select_id() == 2); buffers[2].last_access = 5; clock_value = 6;
	assert(select_id() == 1); buffers[1].last_access = 6;
	buffers[0].last_access = 7; clock_value = 8;
	assert(select_id() == 1); buffers[1].last_access = 8;
	buffers[2].state = 1; clock_value = 9;
	assert(select_id() == 1);
	puts("PASS handout sequence: P3, P2, P5, P6");

	reset(3); assert(select_id() == 1);
	reset(1); assert(select_id() == 0);
	reset(3); buffers[0].state = 1; buffers[1].state = 2; assert(select_id() == 2);
	reset(3); for (int i = 0; i < 3; i++) buffers[i].state = 1;
	if (setjmp(error_target) == 0) { select_id(); assert(!"expected no-unpinned error"); }
	assert(!locks && !allocations && strstr(log_text, "no unpinned buffers available"));
	puts("PASS zero timestamps/ties, one candidate, all pinned");

	for (int mode = 1; mode <= 3; mode++)
	{
		reset(3); for (int i = 0; i < 3; i++) buffers[i].last_access = i + 1;
		clock_value = 4; inject_mode = mode;
		assert(select_id() == 2);
		assert(lock_calls > NBuffers + 1);
	}
	puts("PASS retry after victim pin, victim access, or other candidate access");

	reset(2); buffers[0].state = BM_VALID;
	assert(PinBuffer(&buffers[0], NULL));
	assert(buffers[0].last_access == 1 && clock_value == 2 && refs[0].refcount == 1);
	assert(PinBuffer(&buffers[0], NULL));
	assert(buffers[0].last_access == 2 && clock_value == 3 && refs[0].refcount == 2);
	assert(BUF_STATE_GET_REFCOUNT(buffers[0].state) == 1);
	LockBufHdr(&buffers[1]); PinBuffer_Locked(&buffers[1]);
	assert(!locks && buffers[1].last_access == 3 && clock_value == 4 && refs[1].refcount == 1);
	puts("PASS first pin, repeated hit, locked pin, timestamp lock discipline");

	for (int trial = 0; trial < 2000; trial++)
	{
		int eligible = 0, expected = -1;
		reset(16); clock_value = 100;
		for (int i = 0; i < NBuffers; i++)
		{
			buffers[i].last_access = rand() % 8;
			buffers[i].state = rand() % 3 == 0;
			eligible += !buffers[i].state;
		}
		if (!eligible) buffers[0].state = 0, eligible = 1;
		for (int i = 0; i < NBuffers; i++)
		{
			int rank = 0;
			if (buffers[i].state) continue;
			for (int j = 0; j < NBuffers; j++)
				if (!buffers[j].state && (buffers[j].last_access < buffers[i].last_access ||
					(buffers[j].last_access == buffers[i].last_access && j < i))) rank++;
			if (rank == (eligible > 1 ? 1 : 0)) expected = i;
		}
		assert(select_id() == expected);
	}
	puts("PASS 2000 generated candidate sets against independent rank oracle");
	assert(!locks && !allocations);
	return 0;
}

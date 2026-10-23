"""파이프라인 워밍업 — 첫 화면(로그인)과 로딩을 겹치게 한다.

### 0928 신규

동작
    첫 브라우저 접속 → app.py 가 이 모듈을 import 하고 start() 호출 →
    워커 스레드가 백그라운드로 파이프라인을 만들고 _ready 를 세운다 →
    사용자가 자격증명을 입력하는 동안 로딩이 끝난다 →
    stream_code() 는 _ready 를 확인하고, 아직이면 스피너를 띄우고 기다린다.

안전 가드레일
    로딩이 예외로 죽어도 _ready 는 finally 에서 반드시 세워진다(무한 대기 없음).
    이때 get_pipe() 는 (None, err) 를 돌려주고, stream_code() 는 mock 코드로
    대체하지 않고 PipelineUnavailable 을 올린다 — UI 가 재로딩을 유도한다.

수명주기
    start()   : 로그인 화면 렌더 시점 — 프로세스당 1회 기동(_started 가드)
    discard() : 로그아웃 시점 — 파이프라인 폐기. "로그인마다 새 파이프라인"을 위해
                여섯 가지를 모두 되돌린다(캐시 항목·_pipe·_error·_elapsed·_ready·_started).
                되돌린 뒤에는 app.py 의 다음 리런이 boot.start() 를 다시 통과하면서
                자연스럽게 재기동된다(별도 재기동 호출 불필요).
"""
import threading
import time

import streamlit as st

# 워밍업 대상 모델. get_pipe 기본값과 반드시 일치해야 캐시가 재사용된다.
MODEL = "gpt-4o-mini"

_lock = threading.Lock()
_started = False
_ready = threading.Event()
_pipe = None
_error = None
_elapsed = None


def _warm() -> None:
    """워커 스레드 본체. 실패해도 _ready 를 반드시 세운다."""
    global _pipe, _error, _elapsed
    t0 = time.perf_counter()
    try:
        # agent_bridge 는 모듈 레벨에서 install_local_loader() 를 실행하므로,
        # 여기서 import 하는 것만으로 HF 다운로드 차단이 먼저 걸린다.
        # (모듈 최상위에서 import 하면 agent_bridge ↔ boot 순환이 되므로 함수 안에서.)
        from ui import agent_bridge as ab
        pipe, err = ab.get_pipe(MODEL)
        _pipe, _error = pipe, err
    except Exception as e:  # import 실패까지 포함
        _error = f"{type(e).__name__}: {e}"
    finally:
        _elapsed = time.perf_counter() - t0
        _ready.set()


def start() -> None:
    """로딩 스레드를 프로세스당 1회만 기동한다(리런·재접속에 안전)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_warm, name="dp-pipe-warmup", daemon=True).start()


def discard() -> None:
    """파이프라인을 폐기한다 — 로그아웃 시 호출. 다음 로그인에서 재기동된다.

    ### 0928 추가

    "로그인마다 새 파이프라인" 수명주기를 위한 리셋. 여섯 가지를 모두 되돌려야 한다.
    하나라도 빠지면 조용히 깨진다:

      - ab.get_pipe.clear() : 캐시 항목. 이게 남아 있으면 다음 로그인에서
                              get_pipe() 가 "폐기한 옛 객체"를 그대로 반환해
                              재빌드가 아예 일어나지 않는다. (가장 중요)
      - _pipe               : 전역 강참조 — clear() 만으로는 메모리가 안 풀린다
      - _error              : 이전 실패 메시지가 다음 로그인까지 남는다
      - _elapsed            : status() 가 옛 소요시간을 보고한다
      - _ready              : 남아 있으면 is_ready() 가 즉시 True →
                              스피너를 건너뛰고 "준비 안 된 파이프라인"을 쓴다
      - _started            : False 여야 다음 start() 가 재기동한다

    주의: get_pipe 는 함수 안에서 import 해 호출한다. 모듈 최상위에서
    agent_bridge 를 import 하면 agent_bridge ↔ boot 순환이 된다.
    """
    global _started, _pipe, _error, _elapsed
    with _lock:
        try:
            from ui import agent_bridge as ab
            ab.get_pipe.clear()
        except Exception:
            # agent_bridge 를 못 불러온 상황(의존성 결손 등)이면 캐시도 없다.
            # 폐기 자체는 계속 진행한다 — 남은 전역을 되돌리는 게 더 중요하다.
            pass
        _pipe = None
        _error = None
        _elapsed = None
        _ready.clear()
        _started = False


def is_ready() -> bool:
    """로딩이 끝났는지(성공·실패 무관)."""
    return _ready.is_set()


def wait_ready(timeout: float | None = None) -> bool:
    """로딩 완료까지 블로킹. 이미 끝났으면 즉시 True."""
    return _ready.wait(timeout)


def status() -> tuple[bool, object, str | None, float | None]:
    """(준비여부, pipe, 오류메시지, 소요초). 로딩 전이면 (False, None, None, None)."""
    return _ready.is_set(), _pipe, _error, _elapsed
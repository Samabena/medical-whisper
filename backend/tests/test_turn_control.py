"""LIVE-7.4 — contrôleur de tour & barge-in (annulation propre de la sortie agent)."""

from __future__ import annotations

import asyncio

from app.application.live.turn_control import TurnController, run_cancellable


async def test_barge_in_annule_la_sortie_en_cours():
    joue = asyncio.Event()

    async def longue_sortie() -> None:
        joue.set()
        await asyncio.sleep(10)  # « parle » longtemps

    tc = TurnController(barge_in=True)
    tc.start(longue_sortie())
    await joue.wait()
    assert tc.speaking is True

    interrompu = await tc.on_user_speech()
    assert interrompu is True
    assert tc.speaking is False  # annulée, pas de tâche orpheline


async def test_barge_in_desactive_ne_coupe_pas():
    async def sortie() -> None:
        await asyncio.sleep(10)

    tc = TurnController(barge_in=False)
    tc.start(sortie())
    await asyncio.sleep(0)
    assert await tc.on_user_speech() is False
    assert tc.speaking is True
    await tc.close()  # nettoyage


async def test_nouvelle_sortie_annule_la_precedente():
    async def sortie() -> None:
        await asyncio.sleep(10)

    tc = TurnController()
    tc.start(sortie())
    premiere = tc._task
    tc.start(sortie())  # remplace
    await asyncio.gather(premiere, return_exceptions=True)
    assert premiere.cancelled()
    await tc.close()


async def test_wait_attend_la_fin_naturelle():
    fini = asyncio.Event()

    async def sortie() -> None:
        await asyncio.sleep(0.01)
        fini.set()

    tc = TurnController()
    tc.start(sortie())
    await tc.wait()
    assert fini.is_set()


async def test_run_cancellable_appelle_le_nettoyage():
    nettoye = asyncio.Event()

    async def body() -> None:
        await asyncio.sleep(10)

    async def cleanup() -> None:
        nettoye.set()

    task = asyncio.ensure_future(run_cancellable(body, on_cancel=cleanup))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert nettoye.is_set()

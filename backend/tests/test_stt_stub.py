"""VOX-6.2 — STT stub : séquence partiel stable → endpoint → final, déterministe."""

from __future__ import annotations

from app.application.ports.stt import SttEndpoint, SttFinal, SttPartial
from app.infrastructure.stt.stub import StubSttStream
from app.domain.value_objects import Language


async def test_end_turn_emet_partiel_endpoint_final():
    stream = StubSttStream(utterances=["le patient s'appelle Martin"])
    s = await stream.open(language=Language.FR, hotwords=[])
    await s.send_audio(b"\x00\x01")
    await s.end_turn()

    got = []
    async for ev in s.events():
        got.append(ev)
        if isinstance(ev, SttFinal):
            await s.close()

    assert s.received_frames == [b"\x00\x01"]
    assert isinstance(got[0], SttPartial) and got[0].stable is True
    assert any(isinstance(e, SttEndpoint) for e in got)
    final = got[-1]
    assert isinstance(final, SttFinal)
    assert final.text == "le patient s'appelle Martin"
    assert final.words and all(0 <= w.conf <= 1 for w in final.words)


async def test_hors_script_emet_final_vide():
    stream = StubSttStream(utterances=[])
    s = await stream.open(language=Language.FR, hotwords=[])
    await s.end_turn()
    got = []
    async for ev in s.events():
        got.append(ev)
        if isinstance(ev, SttFinal):
            await s.close()
    # Pas de partiel (texte vide), mais un endpoint + un final vide.
    assert any(isinstance(e, SttEndpoint) for e in got)
    assert isinstance(got[-1], SttFinal) and got[-1].text == ""

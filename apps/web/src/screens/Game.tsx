import { Check, Pause, Volume2, VolumeX, WifiOff, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Duel } from '../components/Duel';
import { EndGameButton } from '../components/EndGame';
import { CountdownRing, GuessModal, HonorClaim, ObjectionBanner, VoiceConfirmModal } from '../components/GameParts';
import { MysteryCard } from '../components/MysteryCard';
import { PlacementSummary } from '../components/PlacementSummary';
import { RevealExplain } from '../components/RevealExplain';
import { TeamPanel } from '../components/TeamPanel';
import { TimelineCarousel } from '../components/TimelineCarousel';
import { HintChooser, HintPanel, HintStrip, TurnTools } from '../components/TurnTools';
import { Button, Card, Screen, TeamShape } from '../components/ui';
import { useCountdown, useHintDeadline, useThrottled, vibrate } from '../hooks/hooks';
import { es } from '../i18n/es';
import { explainResult } from '../lib/explain';
import { snapIndex } from '../lib/groups';
import { colorFor, teamName } from '../lib/teams';
import type { CardPublic, RoomView, TeamView, TurnView } from '../protocol/types';
import { act, canChangePlace, cancelPlace, confirmPlace } from '../store/controller';
import { useRoom } from '../store/room';

function isRevealed(card: TurnView['card']): card is CardPublic {
  return !('hidden' in card);
}

export function Countdown({ view }: { view: RoomView }) {
  const cd = useRoom((s) => s.countdown);
  const s = useCountdown(cd?.deadlineTs ?? null);
  const first = cd ? view.teams[cd.firstSlot] : undefined;
  return (
    <Screen footer={<EndGameButton view={view} />}>
      <div className="relative flex flex-1 flex-col items-center justify-center gap-6 overflow-hidden text-center" role="status">
        <span className="cd-ring" aria-hidden />
        <span className="cd-ring" aria-hidden />
        <p key={s ?? 'x'} className="year cd-num" data-testid="countdown-number">
          {s !== null && s > 0 ? s : '…'}
        </p>
        <p className="relative z-[1] text-xl font-semibold">
          {first ? es.countdown.first(teamName(first)) : es.countdown.ready}
        </p>
      </div>
    </Screen>
  );
}

export function Game({ view }: { view: RoomView }) {
  const turn = view.turn;
  const me = view.you.slot;
  const audioError = useRoom((s) => s.audioError);
  const deckLow = useRoom((s) => s.deckLow);
  const audioStatus = useRoom((s) => s.audioStatus);

  const activeSlot = turn?.teamSlot ?? null;
  const myTurn = me !== null && me === activeSlot;

  // Vibración al cambiar de turno hacia nosotros.
  const lastActive = useRef<number | null>(null);
  useEffect(() => {
    if (activeSlot !== null && lastActive.current !== activeSlot && myTurn && lastActive.current !== null) {
      vibrate([200, 80, 200]);
    }
    if (activeSlot !== null && lastActive.current === null && myTurn) vibrate(200);
    lastActive.current = activeSlot;
  }, [activeSlot, myTurn]);

  if (!turn || activeSlot === null) return null;
  const activeTeam = view.teams[activeSlot];
  if (!activeTeam) return null;

  const paused = view.phase === 'paused';
  const phase = paused ? (view.pause?.resumePhase ?? 'turn_ready') : view.phase;
  const playing = audioStatus?.playing ?? view.audio.playing;

  return (
    <Screen footer={<EndGameButton view={view} />}>
      <div className={view.teams.length > 2 ? 'grid grid-cols-2 gap-x-2 gap-y-3' : 'flex gap-2'} aria-label="Equipos">
        {view.teams.map((t) => (
          <TeamPanel
            key={t.slot}
            team={t}
            target={view.settings.targetCards}
            active={t.slot === activeSlot}
            you={t.slot === me}
          />
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-[22px] font-bold leading-tight" role="status" data-testid="turn-banner">
          {myTurn ? es.game.yourTurn : es.game.turnOf(teamName(activeTeam))}
        </h1>
        {phase !== 'reveal' && turn.startedPlaying && view.audio.paused ? (
          <span className="chip" data-testid="paused-chip">
            <VolumeX size={16} aria-hidden />
            {es.player.pausedChip}
          </span>
        ) : playing && phase !== 'reveal' ? (
          <span className="chip" data-testid="playing-chip">
            <Volume2 size={16} aria-hidden />
            {es.game.playing}
          </span>
        ) : null}
      </div>
      {!myTurn && turn.hints && phase !== 'reveal' ? <HintStrip hints={turn.hints} /> : null}

      {audioError ? (
        <p role="alert" className="notice">
          {es.game.audioProblem[audioError.code] ?? es.game.audioProblem.unknown}
        </p>
      ) : null}
      {deckLow !== null && deckLow < 5 ? (
        <p className="help text-center font-semibold">{es.game.deckLow(deckLow)}</p>
      ) : null}

      {paused ? <PausedCard view={view} /> : null}

      <div
        className={paused ? 'pointer-events-none flex flex-1 flex-col gap-4 opacity-50' : 'flex flex-1 flex-col gap-4'}
        aria-hidden={paused}
      >
        <PhaseBody key={turn.card.instanceId} view={view} turn={turn} phase={phase} activeTeam={activeTeam} myTurn={myTurn} />
      </div>
    </Screen>
  );
}

function PausedCard({ view }: { view: RoomView }) {
  const pause = view.pause;
  const left = useCountdown(pause?.deadlineTs ?? null);
  if (!pause) return null;
  const team = pause.slot !== null ? view.teams[pause.slot] : undefined;
  const iAmThatTeam = pause.slot !== null && pause.slot === view.you.slot;
  let title: string;
  let body: string | null = null;
  if (pause.reason === 'team_offline') {
    title = iAmThatTeam ? es.paused.reconnecting : es.paused.teamOffline(teamName(team, pause.slot ?? 0), left ?? 0);
    body = es.paused.teamOfflineSkip;
  } else if (view.you.isHost) {
    title = es.paused.hostYou;
    body = es.paused.hostYouBody;
  } else {
    title = es.paused.hostOffline;
    body = es.paused.hostOfflineBody;
  }
  const Icon = pause.reason === 'team_offline' ? WifiOff : Pause;
  return (
    <Card className="flex flex-col items-center gap-2 text-center">
      <Icon size={40} className="pause-icon" style={{ color: pause.reason === 'team_offline' ? 'var(--color-magenta-light)' : 'var(--color-primary-light)' }} aria-hidden />
      <p role="alert" className="h2" data-testid="paused">
        {title}
      </p>
      {body ? <p className="text-muted-foreground">{body}</p> : null}
    </Card>
  );
}

interface BodyProps {
  view: RoomView;
  turn: TurnView;
  phase: RoomView['phase'];
  activeTeam: TeamView;
  myTurn: boolean;
}

function PhaseBody(props: BodyProps) {
  const { phase } = props;
  switch (phase) {
    case 'turn_ready':
      return <TurnReady {...props} />;
    case 'placing':
      return <Placing {...props} />;
    case 'guessing':
      return <Guessing {...props} />;
    case 'objection':
      return <Objection {...props} />;
    case 'reveal':
      return <Reveal {...props} />;
    default:
      return null;
  }
}

const mystery = <MysteryCard />;
const noop = () => undefined;

/** Línea de solo lectura para quien no juega: equipo activo con su forma y tres puntos. */
function WaitCard({ team, title, sub }: { team: TeamView; title: string; sub?: string }) {
  const c = colorFor(team);
  return (
    <div className="panel flex items-center gap-3 p-3" style={{ '--tc': c.hex } as React.CSSProperties} data-testid="wait-card">
      <TeamShape shape={c.shape} color={c.hex} size={32} />
      <div className="min-w-0 flex-1">
        <p className="text-xl font-semibold leading-tight">{title}</p>
        {sub ? <p className="help mt-0.5">{sub}</p> : null}
      </div>
      <span className="dots" aria-hidden>
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

function Line({ team, index }: { team: TeamView; index: number }) {
  return <TimelineCarousel cards={team.timeline} mode="readonly" selectedIndex={index} mystery={mystery} />;
}

function TurnReady({ activeTeam, myTurn }: BodyProps) {
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Line team={activeTeam} index={Math.floor(activeTeam.timeline.length / 2)} />
      {myTurn ? (
        <Button
          xl
          busy={busy}
          onClick={() => {
            setBusy(true);
            void act('play_request', {}).then(() => {
              setBusy(false);
            });
          }}
        >
          {es.game.play}
        </Button>
      ) : (
        <WaitCard team={activeTeam} title={es.game.notYourTurn} />
      )}
    </>
  );
}

function Placing({ activeTeam, turn, myTurn, view }: BodyProps) {
  const len = activeTeam.timeline.length;
  // Tras «Cambiar hueco» el servidor conserva el hueco elegido en `previewIndex`.
  const [index, setIndex] = useState(() => turn.previewIndex ?? Math.floor(len / 2));
  const [busy, setBusy] = useState(false);
  const [chooser, setChooser] = useState(false);
  const hints = turn.hints;
  // Al acabarse los 60 s tras una pista se confirma el hueco que haya seleccionado.
  const secs = useHintDeadline(hints?.deadlineTs, view.phase === 'paused', myTurn, () => {
    setBusy(true);
    void confirmPlace(turn.card.instanceId, index);
  });
  const me = view.you.slot;
  const preview = useThrottled((i: number) => {
    void act('place_preview', { index: i });
  }, 4);

  // Primer aviso del hueco inicial.
  useEffect(() => {
    if (myTurn) preview(index);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myTurn]);

  if (!myTurn) {
    return (
      <>
        <TimelineCarousel
          cards={activeTeam.timeline}
          mode="readonly"
          selectedIndex={turn.previewIndex ?? Math.floor(len / 2)}
          mystery={mystery}
        />
        <WaitCard team={activeTeam} title={es.game.notYourTurn} sub={es.game.placingOther(teamName(activeTeam))} />
      </>
    );
  }
  return (
    <>
      <TimelineCarousel
        cards={activeTeam.timeline}
        mode="place"
        equalHint
        selectedIndex={index}
        mystery={mystery}
        onIndexChange={(i) => {
          setIndex(i);
          preview(i);
        }}
      />
      {hints && hints.used.length > 0 ? <HintPanel hints={hints} secs={secs} paused={view.phase === 'paused'} /> : null}
      <TurnTools
        view={view}
        hints
        onHint={() => {
          setChooser(true);
        }}
      />
      {chooser ? (
        <HintChooser
          tokens={me !== null ? (view.teams[me]?.tokens ?? 0) : 0}
          used={(hints?.used ?? []).map((h) => h.kind)}
          onClose={() => {
            setChooser(false);
          }}
        />
      ) : null}
      <div className="grid grid-cols-2 gap-3">
        <Button
          variant="secondary"
          onClick={() => {
            void act('play_request', {});
          }}
        >
          {es.game.repeat}
        </Button>
        <Button
          busy={busy}
          onClick={() => {
            setBusy(true);
            void confirmPlace(turn.card.instanceId, index).then((ok) => {
              if (!ok) setBusy(false);
            });
          }}
        >
          {es.game.anchor}
        </Button>
      </div>
    </>
  );
}

function Guessing({ activeTeam, turn, myTurn, view }: BodyProps) {
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
  const [chooser, setChooser] = useState(false);
  const hints = turn.hints;
  const me = view.you.slot;
  // Al acabarse el límite se envía lo que haya escrito (aunque esté vacío) o la confirmación en voz alta.
  const secs = useHintDeadline(hints?.deadlineTs, view.phase === 'paused', myTurn, () => {
    if (view.settings.mode === 'voice') void act('voice_confirm', {});
    else void act('guess_submit', { title: title.trim(), artist: artist.trim() });
  });
  const place = useRoom((s) => s.place);
  const canChange = canChangePlace(place, turn.card.instanceId, turn);
  const onChangeSlot = canChange
    ? () => {
        void cancelPlace(turn.card.instanceId);
      }
    : undefined;
  const tools = (
    <div className="flex flex-col gap-3">
      {hints && hints.used.length > 0 ? <HintPanel hints={hints} secs={secs} paused={view.phase === 'paused'} /> : null}
      <TurnTools
        view={view}
        hints
        onHint={() => {
          setChooser(true);
        }}
      />
    </div>
  );
  const summary = (
    <PlacementSummary
      team={activeTeam}
      years={activeTeam.timeline.map((c) => c.year)}
      index={turn.placedIndex}
      mine={myTurn}
    />
  );
  return (
    <>
      <TimelineCarousel
        cards={activeTeam.timeline}
        mode="readonly"
        selectedIndex={turn.placedIndex ?? 0}
        mystery={mystery}
      />
      {myTurn ? null : summary}
      <WaitCard team={activeTeam} title={es.game.thinking} />
      {myTurn && chooser ? (
        <HintChooser
          tokens={me !== null ? (view.teams[me]?.tokens ?? 0) : 0}
          used={(hints?.used ?? []).map((h) => h.kind)}
          onClose={() => {
            setChooser(false);
          }}
        />
      ) : myTurn ? (
        view.settings.mode === 'app' ? (
          <GuessModal
            summary={summary}
            tools={tools}
            title={title}
            artist={artist}
            onTitle={setTitle}
            onArtist={setArtist}
            onChangeSlot={onChangeSlot}
          />
        ) : (
          <VoiceConfirmModal summary={summary} tools={tools} onChangeSlot={onChangeSlot} />
        )
      ) : null}
    </>
  );
}

function Objection({ activeTeam, turn, view }: BodyProps) {
  const me = view.you.slot;
  const eligible = me !== null && (turn.eligibleObjectors ?? []).includes(me);
  const [passed, setPassed] = useState(false);
  const placed = turn.placedIndex ?? 0;
  const len = activeTeam.timeline.length;
  const lineYears = useMemo(() => activeTeam.timeline.map((c) => c.year), [activeTeam]);
  const placedStop = snapIndex(lineYears, placed);
  const [index, setIndex] = useState(() => snapIndex(lineYears, placedStop === 0 ? Math.min(1, len) : 0));
  const secs = useCountdown(turn.deadlineTs);
  const objector = turn.objection ? view.teams[turn.objection.slot] : undefined;
  const canObject = eligible && !passed && turn.objection === null;
  const myTeam = me !== null ? view.teams[me] : undefined;
  const myColor = myTeam ? colorFor(myTeam).hex : undefined;
  const summary = (
    <PlacementSummary team={activeTeam} years={lineYears} index={turn.placedIndex} mine={me === activeTeam.slot} />
  );

  // Una sola vibración corta al pasar a «te toca objetar».
  useEffect(() => {
    if (canObject) vibrate(150);
  }, [canObject]);

  if (canObject) {
    return (
      <>
        <ObjectionBanner
          deadlineTs={turn.deadlineTs}
          totalS={view.settings.objectionWindowS}
          title={es.game.objectQuestion}
          body={es.game.objectBody}
          kicker={es.game.objectKicker}
          color={myColor}
        />
        {summary}
        <TimelineCarousel
          cards={activeTeam.timeline}
          mode="object"
          equalHint
          selectedIndex={index}
          blockedIndex={placedStop}
          mystery={mystery}
          onIndexChange={setIndex}
        />
        <div className="grid grid-cols-2 gap-3" style={myColor ? ({ '--tc': myColor } as React.CSSProperties) : undefined}>
          <Button
            variant="secondary"
            onClick={() => {
              setPassed(true);
              void act('objection_pass', {});
            }}
          >
            {es.game.pass}
          </Button>
          <Button
            variant="danger"
            className="btn-pulse"
            disabled={index === placedStop}
            onClick={() => {
              void act('objection', { index });
            }}
          >
            {es.game.objectHere}
          </Button>
        </div>
      </>
    );
  }
  const years = lineYears;
  let reason: string | null = null;
  if (!passed && turn.objection === null && me !== null) {
    reason = me === activeTeam.slot ? es.game.objectOthers : eligible ? null : es.game.objectNoTokens;
  }
  return (
    <>
      {summary}
      <TimelineCarousel cards={activeTeam.timeline} mode="readonly" selectedIndex={placed} mystery={mystery} />
      {me === activeTeam.slot ? <TurnTools view={view} hints={false} onHint={noop} /> : null}
      {turn.objection && objector ? (
        <>
          <Duel
            original={activeTeam}
            objector={objector}
            years={years}
            originalIndex={placed}
            objectionIndex={turn.objection.index}
          />
          <p role="status" className="text-center font-semibold">
            {es.game.objectionIn(teamName(objector))}
          </p>
        </>
      ) : (
        <Card className="flex items-center gap-4">
          <CountdownRing deadlineTs={turn.deadlineTs} totalS={view.settings.objectionWindowS} />
          <div>
            <p role="status" className="h2">
              {passed ? es.game.passed : es.game.waitingObjections(secs ?? 0)}
            </p>
            {reason ? (
              <p className="obj-reason mt-1" data-testid="objection-reason">
                {reason}
              </p>
            ) : null}
          </div>
        </Card>
      )}
    </>
  );
}

function Reveal({ view, turn, activeTeam, myTurn }: BodyProps) {
  const reveal = useRoom((s) => s.reveal);
  const result = turn.result;
  const card = isRevealed(turn.card) ? turn.card : reveal?.card ?? null;
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => {
      setShown(true);
    }, 80);
    return () => {
      clearTimeout(id);
    };
  }, []);
  const secs = useCountdown(turn.revealUnlocksAt);
  const me = view.you.slot;
  const winner = result?.toSlot !== null && result?.toSlot !== undefined ? view.teams[result.toSlot] : undefined;
  const lineTeam = winner ?? activeTeam;
  const cardIndex = useMemo(
    () => lineTeam.timeline.findIndex((c) => c.instanceId === card?.instanceId),
    [lineTeam, card],
  );
  const objector = result?.objectionSlot != null ? view.teams[result.objectionSlot] : undefined;
  const bothOk = result ? result.titleOk && result.artistOk : false;
  const [busy, setBusy] = useState(false);

  const objIndex = turn.objection?.index ?? reveal?.objection_result?.index ?? null;
  const baseYears = useMemo(
    () => activeTeam.timeline.filter((c) => c.instanceId !== card?.instanceId).map((c) => c.year),
    [activeTeam, card],
  );
  const [claimed, setClaimed] = useState(false);
  const explanation = useMemo(
    () =>
      result
        ? explainResult(result, {
            activeName: teamName(activeTeam),
            objectorName: objector ? teamName(objector) : null,
            mode: view.settings.mode,
            honorAnswered: claimed || result.titleOk || result.artistOk,
            viewerIsActive: myTurn,
            lineYears: baseYears,
          })
        : null,
    [result, activeTeam, objector, view.settings.mode, claimed, myTurn, baseYears],
  );
  const showDuel = Boolean(objector && result && objIndex !== null && turn.placedIndex !== null);

  return (
    <>
      <div className="flex justify-center" data-testid="reveal-card">
        <MysteryCard card={shown ? card : null} large />
      </div>

      <PlacementSummary team={activeTeam} years={baseYears} index={turn.placedIndex} mine={myTurn} />

      {showDuel && objector && result && objIndex !== null ? (
        <Duel
          original={activeTeam}
          objector={objector}
          years={baseYears}
          originalIndex={turn.placedIndex ?? 0}
          objectionIndex={objIndex}
          result={{ outcome: result.outcome, objectionOk: result.objectionOk }}
        />
      ) : null}

      {result && explanation ? (
        <RevealExplain
          explanation={explanation}
          active={activeTeam}
          objector={objector ?? null}
          hidePending={view.settings.mode === 'voice' && myTurn}
        />
      ) : null}

      {result && view.settings.mode === 'app' ? (
        <Card className="flex flex-col gap-1 text-sm" data-testid="reveal-guess">
          {turn.guess ? (
            <p>
              <span className="font-bold">{es.game.yourAnswer}:</span> {turn.guess.title || '—'} /{' '}
              {turn.guess.artist || '—'}
            </p>
          ) : null}
          <p className="flex flex-wrap gap-3 font-bold">
            <Mark ok={result.titleOk} label={es.game.guessTitleOk} />
            <Mark ok={result.artistOk} label={es.game.guessArtistOk} />
          </p>
        </Card>
      ) : null}

      {view.settings.mode === 'voice' && myTurn && result ? (
        <HonorClaim
          initialTitle={result.titleOk}
          initialArtist={result.artistOk}
          onClaim={() => {
            setClaimed(true);
          }}
        />
      ) : null}

      {view.settings.mode === 'app' && me !== null && result && !bothOk ? (
        <div className="flex flex-col gap-2">
          <Button
            variant="accent"
            onClick={() => {
              void act('accept_guess', {});
            }}
          >
            {es.game.acceptGuess}
          </Button>
          <p className="help text-center">{es.game.acceptHint}</p>
        </div>
      ) : null}

      <TimelineCarousel
        cards={lineTeam.timeline}
        mode="readonly"
        selectedIndex={Math.max(0, cardIndex)}
        highlightId={card?.instanceId ?? null}
      />

      {myTurn ? (
        <Button
          xl
          busy={busy}
          disabled={secs !== null && secs > 0}
          onClick={() => {
            setBusy(true);
            void act('next_turn', {}).then((ok) => {
              if (!ok) setBusy(false);
            });
          }}
        >
          {secs !== null && secs > 0 ? es.game.nextIn(secs) : es.game.next}
        </Button>
      ) : (
        <p className="text-center font-semibold text-muted-foreground">{es.game.waitNext(teamName(activeTeam))}</p>
      )}
    </>
  );
}

function Mark({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1">
      {ok ? (
        <Check size={16} className="text-accent" aria-hidden />
      ) : (
        <X size={16} className="text-magenta-light" aria-hidden />
      )}
      {label}
    </span>
  );
}

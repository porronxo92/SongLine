import { Check, Coins, Volume2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { CountdownRing, GuessModal, HonorClaim, ObjectionBanner, VoiceConfirmModal } from '../components/GameParts';
import { MysteryCard } from '../components/MysteryCard';
import { TeamPanel } from '../components/TeamPanel';
import { TimelineCarousel } from '../components/TimelineCarousel';
import { Button, Card, Screen } from '../components/ui';
import { useCountdown, useThrottled, vibrate } from '../hooks/hooks';
import { es } from '../i18n/es';
import { teamName } from '../lib/teams';
import type { CardPublic, RoomView, TeamView, TurnView } from '../protocol/types';
import { act } from '../store/controller';
import { useRoom } from '../store/room';

function isRevealed(card: TurnView['card']): card is CardPublic {
  return !('hidden' in card);
}

export function Countdown({ view }: { view: RoomView }) {
  const cd = useRoom((s) => s.countdown);
  const s = useCountdown(cd?.deadlineTs ?? null);
  const first = cd ? view.teams[cd.firstSlot] : undefined;
  return (
    <Screen>
      <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center" role="status">
        <p className="year text-[9rem] leading-none text-primary" data-testid="countdown-number">
          {s !== null && s > 0 ? s : '…'}
        </p>
        <p className="font-display text-2xl font-semibold">
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
    <Screen>
      <div className="flex gap-2" aria-label="Equipos">
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
        <h1 className="font-display text-2xl font-semibold" role="status" data-testid="turn-banner">
          {myTurn ? es.game.yourTurn : es.game.turnOf(teamName(activeTeam))}
        </h1>
        {playing && phase !== 'reveal' ? (
          <span className="chip" data-testid="playing-chip">
            <Volume2 size={16} aria-hidden />
            {es.game.playing}
          </span>
        ) : null}
      </div>

      {audioError ? (
        <p role="alert" className="rounded-sm bg-amber-100 p-3 font-semibold text-amber-950">
          {es.game.audioProblem[audioError.code] ?? es.game.audioProblem.unknown}
        </p>
      ) : null}
      {deckLow !== null && deckLow < 5 ? (
        <p className="text-center text-sm font-semibold text-muted-foreground">{es.game.deckLow(deckLow)}</p>
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
  return (
    <Card className="text-center" >
      <p role="alert" className="font-display text-xl font-semibold" data-testid="paused">
        {title}
      </p>
      {body ? <p className="text-sm text-muted-foreground">{body}</p> : null}
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
        <p className="text-center text-lg font-semibold">{es.game.notYourTurn}</p>
      )}
    </>
  );
}

function Placing({ activeTeam, turn, myTurn }: BodyProps) {
  const len = activeTeam.timeline.length;
  const [index, setIndex] = useState(() => Math.floor(len / 2));
  const [busy, setBusy] = useState(false);
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
        <p className="text-center text-lg font-semibold">{es.game.placingOther(teamName(activeTeam))}</p>
      </>
    );
  }
  return (
    <>
      <TimelineCarousel
        cards={activeTeam.timeline}
        mode="place"
        selectedIndex={index}
        mystery={mystery}
        onIndexChange={(i) => {
          setIndex(i);
          preview(i);
        }}
      />
      <div className="grid grid-cols-2 gap-3">
        <Button
          variant="soft"
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
            void act('place_confirm', { index }).then((ok) => {
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
  return (
    <>
      <TimelineCarousel
        cards={activeTeam.timeline}
        mode="readonly"
        selectedIndex={turn.placedIndex ?? 0}
        mystery={mystery}
      />
      <p className="text-center text-lg font-semibold">{es.game.thinking}</p>
      {myTurn ? view.settings.mode === 'app' ? <GuessModal /> : <VoiceConfirmModal /> : null}
    </>
  );
}

function Objection({ activeTeam, turn, view }: BodyProps) {
  const me = view.you.slot;
  const eligible = me !== null && (turn.eligibleObjectors ?? []).includes(me);
  const [passed, setPassed] = useState(false);
  const placed = turn.placedIndex ?? 0;
  const len = activeTeam.timeline.length;
  const [index, setIndex] = useState(() => (placed === 0 ? Math.min(1, len) : 0));
  const secs = useCountdown(turn.deadlineTs);
  const objector = turn.objection ? view.teams[turn.objection.slot] : undefined;
  const canObject = eligible && !passed && turn.objection === null;

  if (canObject) {
    return (
      <>
        <ObjectionBanner
          deadlineTs={turn.deadlineTs}
          totalS={view.settings.objectionWindowS}
          title={es.game.objectQuestion}
          body={es.game.objectBody}
        />
        <TimelineCarousel
          cards={activeTeam.timeline}
          mode="object"
          selectedIndex={index}
          blockedIndex={placed}
          mystery={mystery}
          onIndexChange={setIndex}
        />
        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="soft"
            onClick={() => {
              setPassed(true);
              void act('objection_pass', {});
            }}
          >
            {es.game.pass}
          </Button>
          <Button
            variant="pink"
            disabled={index === placed}
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
  return (
    <>
      <TimelineCarousel cards={activeTeam.timeline} mode="readonly" selectedIndex={placed} mystery={mystery} />
      <Card className="flex items-center gap-4">
        <CountdownRing deadlineTs={turn.deadlineTs} totalS={view.settings.objectionWindowS} />
        <p role="status" className="font-display text-xl font-semibold">
          {turn.objection && objector
            ? es.game.objectionIn(teamName(objector))
            : passed
              ? es.game.passed
              : es.game.waitingObjections(secs ?? 0)}
        </p>
      </Card>
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

  return (
    <>
      <div className="flex justify-center" data-testid="reveal-card">
        <MysteryCard card={shown ? card : null} large />
      </div>

      {result ? (
        <Card className="flex flex-col gap-2" data-testid="reveal-result">
          <p className="flex items-center gap-2 font-bold" role="status">
            {result.placedOk ? (
              <Check className="text-green-700" aria-hidden />
            ) : (
              <X className="text-destructive" aria-hidden />
            )}
            {result.placedOk ? es.game.revealPlacedOk : es.game.revealPlacedKo}
          </p>
          {objector ? (
            <p className="font-semibold">
              {result.objectionOk
                ? es.game.objectionRight(teamName(objector))
                : es.game.objectionWrong(teamName(objector))}
            </p>
          ) : null}
          <p className="font-bold">
            {result.outcome === 'kept'
              ? es.game.outcomeKept(teamName(activeTeam))
              : result.outcome === 'stolen' && winner
                ? es.game.outcomeStolen(teamName(winner))
                : es.game.outcomeDiscarded}
          </p>
          {view.settings.mode === 'app' ? (
            <div className="flex flex-col gap-1 text-sm">
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
            </div>
          ) : null}
          {result.tokenAwarded ? (
            <p className="flex items-center gap-2 font-bold text-amber-800">
              <Coins size={18} aria-hidden />
              {es.game.tokenWon}
            </p>
          ) : null}
          {objector ? (
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Coins size={16} aria-hidden />
              {es.game.tokenLost(teamName(objector))}
            </p>
          ) : null}
        </Card>
      ) : null}

      {view.settings.mode === 'voice' && myTurn && result ? (
        <HonorClaim initialTitle={result.titleOk} initialArtist={result.artistOk} />
      ) : null}

      {view.settings.mode === 'app' && me !== null && result && !bothOk ? (
        <div className="flex flex-col gap-1">
          <Button
            variant="violet"
            onClick={() => {
              void act('accept_guess', {});
            }}
          >
            {es.game.acceptGuess}
          </Button>
          <p className="text-center text-xs text-muted-foreground">{es.game.acceptHint}</p>
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
      {ok ? <Check size={16} className="text-green-700" aria-hidden /> : <X size={16} className="text-destructive" aria-hidden />}
      {label}
    </span>
  );
}

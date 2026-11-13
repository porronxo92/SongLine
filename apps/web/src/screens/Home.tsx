import { ArrowRight, Check, CircleHelp, Plus, RotateCcw, Users } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { HowToPlay } from '../components/HowToPlay';
import { Button } from '../components/ui';
import { es } from '../i18n/es';
import { getStoredRoom, setStoredRoom } from '../lib/session';
import '../styles/landing.css';

const copy = es.showcase;

/** A self-contained example, independent from the live game and its hidden song data. */
function TimelineDemo() {
  const [choice, setChoice] = useState<number | null>(null);
  const firstChoice = useRef<HTMLButtonElement>(null);
  const revealed = choice !== null;
  const options = [copy.demoBefore, copy.demoBetween, copy.demoAfter];
  const shortOptions = [copy.demoBeforeShort, copy.demoBetweenShort, copy.demoAfterShort];
  return (
    <section className="sl-demo" aria-labelledby="demo-heading" data-testid="timeline-demo">
      <div className="sl-demo-caption">
        <span className="sl-eyebrow">
          <span className="sl-status-dot" />
          {copy.demoLabel}
        </span>
        <span className="sl-demo-sample">{copy.demoSample}</span>
      </div>
      <div className="sl-demo-stage">
        <svg className="sl-demo-orbits" viewBox="0 0 960 330" fill="none" aria-hidden="true">
          <ellipse cx="480" cy="170" rx="415" ry="130" />
          <ellipse cx="480" cy="170" rx="345" ry="100" />
          <path d="M104 91v22m-11-11h22M838 225v26m-13-13h26M754 51l5 11 12 2-9 9 2 12-10-6-11 6 2-12-9-9 12-2Z" />
        </svg>
        <div className="sl-demo-reference sl-demo-reference-first">
          <span className="sl-demo-decade">80s</span>
          <span className="sl-demo-reference-year">1982</span>
          <strong>{copy.demoFirstSong}</strong>
          <span>{copy.demoFirstArtist}</span>
        </div>
        <div className="sl-demo-sleeve" data-revealed={revealed}>
          <div className="sl-demo-record" aria-hidden="true">
            <span />
            <i />
          </div>
          <div className="sl-demo-card">
            <div className="sl-demo-card-front" aria-hidden={revealed}>
              <img src="/logo/songline-mark.svg" alt="" width={38} height={38} />
              <span className="sl-demo-question">?</span>
              <span className="sl-demo-card-song">{copy.demoSong}</span>
              <span className="sl-demo-card-artist">{copy.demoArtist}</span>
            </div>
            <div className="sl-demo-card-back" aria-hidden={!revealed}>
              <span className="sl-demo-card-decade">90s</span>
              <span className="sl-demo-year">{revealed ? '1996' : ''}</span>
              <span className="sl-demo-card-song">{copy.demoSong}</span>
              <span className="sl-demo-card-artist">{copy.demoArtist}</span>
            </div>
          </div>
        </div>
        <div className="sl-demo-reference sl-demo-reference-last">
          <span className="sl-demo-decade">90s</span>
          <span className="sl-demo-reference-year">1998</span>
          <strong>{copy.demoLastSong}</strong>
          <span>{copy.demoLastArtist}</span>
        </div>
        <div className="sl-demo-track" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="sl-demo-controls">
        <h2 id="demo-heading">{copy.demoPrompt}</h2>
        <p className="sl-demo-instruction">{copy.demoHint}</p>
        <div className="sl-demo-options" role="group" aria-label={copy.demoPrompt}>
          {options.map((option, index) => (
            <button
              key={option}
              ref={index === 0 ? firstChoice : undefined}
              type="button"
              className="sl-demo-choice"
              aria-label={option}
              aria-pressed={choice === index}
              aria-disabled={revealed}
              data-chosen={choice === index}
              data-answer={revealed && index === 1}
              onClick={() => {
                if (!revealed) setChoice(index);
              }}
            >
              <span className="sl-demo-choice-mark" aria-hidden="true">
                {revealed && index === 1 ? <Check size={16} /> : '+'}
              </span>
              <span className="sl-demo-choice-full">{option}</span>
              <span className="sl-demo-choice-short" aria-hidden="true">
                {shortOptions[index]}
              </span>
            </button>
          ))}
        </div>
        <div className="sl-demo-result" aria-live="polite" aria-atomic="true">
          {revealed ? (
            <>
              <p>
                <strong>{choice === 1 ? copy.demoCorrect : copy.demoIncorrect}</strong>{' '}
                <span>{copy.demoAnswer}</span>
              </p>
              <button
                type="button"
                className="sl-text-button"
                onClick={() => {
                  setChoice(null);
                  firstChoice.current?.focus();
                }}
              >
                <RotateCcw size={15} aria-hidden="true" />
                {copy.demoRetry}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function ListenArt() {
  return (
    <div className="sl-art sl-art-listen" aria-hidden="true">
      <div className="sl-art-grid" />
      <span className="sl-art-side-label">{copy.listenArt}</span>
      <div className="sl-vinyl">
        <div className="sl-vinyl-label">
          <span>SL</span>
          <i />
        </div>
      </div>
      <div className="sl-waveform">
        {[22, 38, 16, 52, 72, 38, 58, 86, 46, 68, 32, 56, 80, 42, 60, 26, 46, 18].map((height, index) => (
          <i key={index} style={{ height: `${String(height)}%` }} />
        ))}
      </div>
      <span className="sl-art-sticker">A / B</span>
    </div>
  );
}

function PlaceArt() {
  return (
    <div className="sl-art sl-art-place" aria-hidden="true">
      <span className="sl-art-side-label">{copy.placeArt}</span>
      <div className="sl-art-time-line" />
      <div className="sl-art-year sl-art-year-one">
        <span>80s</span>
        <strong>1982</strong>
        <small>{copy.demoFirstSong}</small>
      </div>
      <div className="sl-art-year sl-art-year-two">
        <span>90s</span>
        <strong>1996</strong>
        <small>{copy.demoSong}</small>
      </div>
      <div className="sl-art-year sl-art-year-three">
        <span>90s</span>
        <strong>1998</strong>
        <small>{copy.demoLastSong}</small>
      </div>
      <span className="sl-art-place-check">
        <Check size={24} />
      </span>
    </div>
  );
}

function ChallengeArt() {
  return (
    <div className="sl-art sl-art-challenge" aria-hidden="true">
      <span className="sl-art-side-label">{copy.challengeArt}</span>
      <svg className="sl-art-challenge-path" viewBox="0 0 360 240" fill="none">
        <path d="M53 160C10 57 182 44 186 113c4 69 143 90 132-22" />
        <path d="m303 99 16-15 8 22" />
      </svg>
      <div className="sl-token sl-token-back">
        <span>?</span>
      </div>
      <div className="sl-token sl-token-front">
        <span>!</span>
      </div>
      <span className="sl-token-mini sl-token-mini-one" />
      <span className="sl-token-mini sl-token-mini-two" />
    </div>
  );
}

function PackArt() {
  return (
    <div className="sl-pack-art" aria-hidden="true">
      <div className="sl-pack-cover sl-pack-rock">
        <span className="sl-pack-top">SONGLINE / 02</span>
        <strong>{copy.packRock}</strong>
        <div className="sl-pack-zigzag" />
        <span className="sl-pack-bottom">{copy.packUpcoming}</span>
      </div>
      <div className="sl-pack-cover sl-pack-spanish">
        <span className="sl-pack-top">SONGLINE / 03</span>
        <strong>{copy.packSpanish}</strong>
        <div className="sl-pack-sun" />
        <span className="sl-pack-bottom">{copy.packUpcoming}</span>
      </div>
      <div className="sl-pack-cover sl-pack-mix">
        <span className="sl-pack-top">SONGLINE / 01</span>
        <strong>{copy.packMix}</strong>
        <div className="sl-pack-disc" />
        <span className="sl-pack-bottom">{copy.packIncluded}</span>
      </div>
    </div>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const [stored, setStored] = useState(getStoredRoom);
  const [rules, setRules] = useState(false);
  const closeRules = useCallback(() => {
    setRules(false);
  }, []);
  return (
    <div className="sl-home">
      <a href="#contenido" className="sl-skip-link">
        {copy.skip}
      </a>
      <header className="sl-nav sl-container">
        <Link className="sl-brand" to="/" aria-label={es.appName}>
          <img className="sl-brand-mark" src="/logo/songline-mark.svg" alt="" width={34} height={34} />
          <img
            className="sl-brand-wordmark"
            src="/logo/songline-wordmark.svg"
            alt=""
            width={138}
            height={26}
          />
        </Link>
        <nav className="sl-nav-links" aria-label={copy.navLabel}>
          <a href="#el-juego">{copy.navGame}</a>
          <a href="#experiencia">{copy.navExperience}</a>
        </nav>
        <Link className="sl-nav-account" to="/cuenta">
          {es.account.title}
          <ArrowRight size={17} aria-hidden="true" />
        </Link>
      </header>
      <main id="contenido" tabIndex={-1}>
        <section className="sl-hero sl-container" id="el-juego" aria-labelledby="home-heading">
          <p className="sl-eyebrow sl-hero-eyebrow">
            <span className="sl-status-dot" />
            {copy.eyebrow}
          </p>
          <h1 id="home-heading">
            {copy.title}
            <br />
            <span>{copy.titleAccent}</span>
          </h1>
          <div className="sl-actions" data-testid="home-actions">
            {stored ? (
              <Button
                variant="accent"
                onClick={() => {
                  navigate(`/sala/${stored}`);
                }}
              >
                {es.home.resume(stored)}
                <ArrowRight size={20} aria-hidden="true" />
              </Button>
            ) : null}
            <Button
              variant={stored ? 'secondary' : 'primary'}
              onClick={() => {
                navigate('/crear');
              }}
            >
              <Plus size={20} aria-hidden="true" />
              {es.home.create}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                navigate('/unirse');
              }}
            >
              <Users size={20} aria-hidden="true" />
              {es.home.join}
            </Button>
          </div>
          {stored ? (
            <button
              className="sl-text-button sl-forget"
              type="button"
              onClick={() => {
                setStoredRoom(null);
                setStored(null);
              }}
            >
              {es.home.forget}
            </button>
          ) : null}
          <p className="sl-action-hint">{copy.actionHint}</p>
          <TimelineDemo />
        </section>
        <section className="sl-experience sl-container" id="experiencia" aria-labelledby="experience-heading">
          <div className="sl-section-heading">
            <p className="sl-eyebrow">{copy.experienceEyebrow}</p>
            <h2 id="experience-heading">
              {copy.experienceTitle}
              <br />
              <span>{copy.experienceAccent}</span>
            </h2>
            <p>{copy.experienceIntro}</p>
          </div>
          <div className="sl-feature-grid">
            <article className="sl-feature">
              <ListenArt />
              <div className="sl-feature-copy">
                <p className="sl-eyebrow">{copy.listenNumber}</p>
                <h3>{copy.listenTitle}</h3>
                <p>{copy.listenCopy}</p>
              </div>
            </article>
            <article className="sl-feature">
              <PlaceArt />
              <div className="sl-feature-copy">
                <p className="sl-eyebrow">{copy.placeNumber}</p>
                <h3>{copy.placeTitle}</h3>
                <p>{copy.placeCopy}</p>
              </div>
            </article>
            <article className="sl-feature">
              <ChallengeArt />
              <div className="sl-feature-copy">
                <p className="sl-eyebrow">{copy.challengeNumber}</p>
                <h3>{copy.challengeTitle}</h3>
                <p>{copy.challengeCopy}</p>
              </div>
            </article>
          </div>
          <div className="sl-wide-grid">
            <article className="sl-social-panel">
              <img
                src="/images/songline-game-night.webp"
                srcSet="/images/songline-game-night-small.webp 768w, /images/songline-game-night.webp 1536w"
                sizes="(max-width: 600px) 100vw, (max-width: 1200px) 50vw, 568px"
                alt={copy.socialAlt}
                width={1536}
                height={1024}
                loading="lazy"
                decoding="async"
              />
              <div className="sl-social-copy">
                <p className="sl-eyebrow">{copy.socialEyebrow}</p>
                <h3>{copy.socialTitle}</h3>
                <p>{copy.socialCopy}</p>
              </div>
            </article>
            <article className="sl-collection-panel">
              <PackArt />
              <div className="sl-collection-copy">
                <p className="sl-eyebrow">{copy.packsEyebrow}</p>
                <h3>{copy.packsTitle}</h3>
                <p>{copy.packsCopy}</p>
              </div>
            </article>
          </div>
        </section>
        <section className="sl-free-band sl-container" aria-labelledby="free-heading">
          <div>
            <p className="sl-eyebrow">{copy.freeEyebrow}</p>
            <h2 id="free-heading">{copy.freeTitle}</h2>
            <p>{copy.freeCopy}</p>
          </div>
          <Link to="/planes" className="sl-free-plans">
            {copy.freePlans}
            <ArrowRight size={20} aria-hidden="true" />
          </Link>
        </section>
      </main>
      <footer className="sl-footer sl-container">
        <div className="sl-footer-brand">
          <img src="/logo/songline-wordmark.svg" alt={es.appName} width={138} height={26} />
          <p>{copy.footerNote}</p>
        </div>
        <p className="sl-copyright">{copy.copyright(new Date().getFullYear())}</p>
        <button
          className="sl-footer-help"
          type="button"
          data-testid="howto-open"
          onClick={() => {
            setRules(true);
          }}
        >
          <CircleHelp size={18} aria-hidden="true" />
          {es.home.howTo}
        </button>
      </footer>
      {rules ? <HowToPlay onClose={closeRules} /> : null}
    </div>
  );
}

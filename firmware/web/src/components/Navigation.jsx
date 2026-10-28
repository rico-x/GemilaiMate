import { useLocation } from 'preact-iso';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faHome } from '@fortawesome/free-solid-svg-icons/faHome';
import { faList } from '@fortawesome/free-solid-svg-icons/faList';
import { faTimeline } from '@fortawesome/free-solid-svg-icons/faTimeline';
import { faCog } from '@fortawesome/free-solid-svg-icons/faCog';
import { faMagnifyingGlassChart } from '@fortawesome/free-solid-svg-icons/faMagnifyingGlassChart';
import { faChartSimple } from '@fortawesome/free-solid-svg-icons/faChartSimple';
import { faCircleChevronLeft } from '@fortawesome/free-solid-svg-icons/faCircleChevronLeft';
import { faCircleChevronRight } from '@fortawesome/free-solid-svg-icons/faCircleChevronRight';
import { GmLogoIcon } from '../pages/ShotAnalyzer/components/SourceMarker.jsx';
import { faGithub } from '@fortawesome/free-brands-svg-icons/faGithub';
import { useEffect, useMemo, useRef } from 'preact/hooks';
import { faPencil } from '@fortawesome/free-solid-svg-icons/faPencil';
import { faCheck } from '@fortawesome/free-solid-svg-icons/faCheck';
import {
  DASHBOARD_MODES,
  dashboardModeSignal,
  setDashboardMode,
} from '../utils/dashboardManager.js';
import { machine } from '../services/ApiService.js';
import { computed } from '@preact/signals';

// List of random icons to display - add your icons here (SVG strings, text, or emojis)
const RANDOM_ICONS = [
  '🍝',
  '🍕',
  '☕️',
  '🥐',
  '🤌',
  <svg
    key='heart'
    xmlns='http://www.w3.org/2000/svg'
    viewBox='0 0 20 20'
    fill='currentColor'
    aria-hidden='true'
    className='text-error size-4'
  >
    <path d='M9.653 16.915l-.005-.003-.019-.01a20.759 20.759 0 01-1.162-.682 22.045 22.045 0 01-2.582-1.9C4.045 12.733 2 10.352 2 7.5a4.5 4.5 0 018-2.828A4.5 4.5 0 0118 7.5c0 2.852-2.044 5.233-3.885 6.82a22.049 22.049 0 01-3.744 2.582l-.019.01-.005.003h-.002a.739.739 0 01-.69.001l-.002-.001z' />
  </svg>,
];

function getRandomIcon() {
  const randomIndex = Math.floor(Math.random() * RANDOM_ICONS.length);
  return RANDOM_ICONS[randomIndex];
}

const update = computed(() => machine.value.status.update);

const NAVIGATION_SECTIONS = [
  {
    id: 'dashboard',
    showDivider: true,
    items: [
      {
        label: 'Dashboard',
        link: '/',
        icon: faHome,
        editLink: '/dashboard-settings',
        editIcon: faPencil,
      },
    ],
  },
  {
    id: 'analysis',
    showDivider: true,
    items: [
      { label: 'Profiles', link: '/profiles', icon: faList },
      { label: 'Shot History', link: '/history', icon: faTimeline },
      { label: 'Shot Analyzer', link: '/analyzer', icon: faMagnifyingGlassChart, isNew: false },
      { label: 'Statistics', link: '/statistics', icon: faChartSimple, isNew: false },
    ],
  },
  {
    id: 'settings',
    showDivider: true,
    items: [{ label: 'Settings', link: '/settings', icon: faCog }],
  },
];

function DashboardModeDropdown({ editLink, editIcon, editActive, isActive }) {
  const mode = dashboardModeSignal.value;

  // daisyUI dropdowns are focus-driven — blur to close after a selection.
  const selectMode = value => {
    setDashboardMode(value);
    document.activeElement?.blur();
  };

  const options = [
    { value: DASHBOARD_MODES.SIMPLE, label: 'Simple' },
    { value: DASHBOARD_MODES.ADVANCED, label: 'Advanced' },
  ];

  return (
    <div className='dropdown dropdown-end h-full'>
      {/* div+tabindex instead of <button>: Safari doesn't focus buttons on click,
          which daisyUI's focus-driven dropdown relies on. */}
      <div
        tabIndex={0}
        role='button'
        aria-label='Dashboard view'
        title='Dashboard view'
        className={`flex h-full cursor-pointer items-center justify-center rounded-r-xl px-2.5 ${
          editActive
            ? 'bg-primary text-primary-content'
            : isActive
              ? 'bg-primary text-primary-content/50 hover:text-primary-content'
              : 'text-base-content/30 hover:bg-base-content/10 hover:text-base-content bg-transparent'
        }`}
      >
        <FontAwesomeIcon icon={editIcon} className='h-3 w-3' />
      </div>
      <ul
        tabIndex={0}
        className='dropdown-content menu bg-base-100 rounded-box border-base-300 z-10 mt-1 w-44 border p-2 shadow-lg'
      >
        {options.map(option => (
          <li key={option.value}>
            <button type='button' onClick={() => selectMode(option.value)}>
              <span className='flex-grow'>{option.label}</span>
              {mode === option.value && <FontAwesomeIcon icon={faCheck} className='h-3 w-3' />}
            </button>
          </li>
        ))}
        <li>
          <a href={editLink} onClick={() => selectMode(DASHBOARD_MODES.CUSTOM)}>
            <span className='flex-grow'>Customize</span>
            {mode === DASHBOARD_MODES.CUSTOM && (
              <FontAwesomeIcon icon={faCheck} className='h-3 w-3' />
            )}
          </a>
        </li>
      </ul>
    </div>
  );
}

function MenuItem({
  collapsed = false,
  icon,
  isNew = false,
  isUnread = false,
  label,
  link,
  editLink,
  editIcon,
}) {
  const { path } = useLocation();
  const isActive = path === link;
  const editActive = path === editLink;
  const isExpanded = collapsed === false;
  const editLinkEnabled = editLink && editIcon && !collapsed;
  // Rounding lives on the children — the row wrapper can't use overflow-hidden
  // or it would clip the dashboard-mode dropdown.
  const commonClasses = `btn btn-md border-none h-12 ${editLinkEnabled ? 'rounded-l-xl rounded-r-none' : 'rounded-xl'}`;
  const baseClassName = collapsed
    ? 'btn-square min-h-0 min-w-0 bg-transparent px-0 text-base-content hover:bg-base-content/10 hover:text-base-content'
    : 'justify-start gap-3 text-base-content hover:text-base-content hover:bg-base-content/10 bg-transparent border-none px-2';
  const activeClassName = collapsed
    ? 'btn-square min-h-0 min-w-0 bg-primary px-0 text-primary-content hover:bg-primary hover:text-primary-content'
    : 'justify-start gap-3 bg-primary text-primary-content hover:bg-primary hover:text-primary-content px-2';
  const className = `${commonClasses} ${isActive ? activeClassName : baseClassName}`;

  return (
    <div className={`flex h-12 flex-row ${collapsed ? 'w-12' : 'w-full'}`}>
      <a
        href={link}
        className={`flex-grow ${className} relative`}
        aria-label={collapsed ? label : undefined}
        aria-current={isActive ? 'page' : undefined}
        title={collapsed ? label : undefined}
      >
        <FontAwesomeIcon size='md' icon={icon} />
        {isUnread && (
          <span className='indicator-item status status-warning absolute -top-0 -right-0' />
        )}
        {isExpanded ? (
          <div className='indicator'>
            {isNew ? (
              <span className='indicator-item text-success pl-8 text-xs font-bold'>NEW</span>
            ) : null}
            <span>{label}</span>
          </div>
        ) : null}
      </a>
      {editLinkEnabled && (
        <DashboardModeDropdown
          editLink={editLink}
          editIcon={editIcon}
          editActive={editActive}
          isActive={isActive}
        />
      )}
    </div>
  );
}

export function Navigation({ collapsed = false, onToggleCollapsed }) {
  // Compute the icon once per mount so the avatar doesn't reshuffle on every render.
  const randomIcon = useMemo(() => getRandomIcon(), []);
  const loc = useLocation();

  // Track the previous route so the collapse-on-navigation effect only fires
  // when the route actually changes, not when `collapsed` flips back to false
  // (which would close the menu immediately after the user opens it on mobile).
  const previousPathRef = useRef(loc.path);

  useEffect(() => {
    const pathChanged = previousPathRef.current !== loc.path;
    previousPathRef.current = loc.path;
    // Re-check viewport width INSIDE the effect (was captured once at module
    // init, so iPad orientation changes were ignored).
    const isMdDown = typeof window !== 'undefined' && window.innerWidth < 768;
    if (pathChanged && !collapsed && isMdDown) {
      onToggleCollapsed();
    }
  }, [loc.path, collapsed, onToggleCollapsed]);

  return (
    <>
      {!collapsed && (
        <div
          className='fixed end-0 top-0 bottom-0 left-0 z-9998 cursor-pointer backdrop-blur-sm backdrop-brightness-50 md:hidden'
          onClick={onToggleCollapsed}
        />
      )}
      <aside
        className={`sidebar border-base-300 bg-base-100 fixed top-0 left-0 z-9999 flex h-screen flex-col overflow-y-auto border-r p-5 md:static landscape:static ${
          collapsed ? 'hidden md:flex md:w-[90px] landscape:flex landscape:w-[90px]' : 'w-[290px]'
        }`}
      >
        <div className='flex h-full flex-col'>
          <div>
            <div
              className={`align-center flex h-12 flex-row items-center justify-center gap-2 ${collapsed ? 'w-12' : 'w-full'}`}
            >
              <GmLogoIcon width={30} height={30} />
              {collapsed ? null : (
                <span className='text-xl font-semibold tracking-tight'>GemilaiMate</span>
              )}
            </div>
          </div>
          {NAVIGATION_SECTIONS.map(section => (
            <div key={section.id}>
              {section.showDivider ? <hr className='h-5 border-0' /> : null}
              <div className='space-y-1.5'>
                {section.items.map(item => {
                  return (
                    <MenuItem
                      key={item.link}
                      collapsed={collapsed}
                      isUnread={item.link === '/settings' && update.value}
                      {...item}
                    />
                  );
                })}
              </div>
            </div>
          ))}

          <div className='flex-grow'>&nbsp;</div>

          {!collapsed && (
            <>
              <div className='flex flex-row items-center justify-center gap-2'>
                <div className='relative inline-block'>
                  <a
                    aria-label='github'
                    rel='noopener noreferrer'
                    href='https://github.com/Rico-X/GemilaiMate'
                    target='_blank'
                    className='btn btn-sm btn-circle text-base-content hover:text-base-content hover:bg-base-content/10 border-none bg-transparent'
                  >
                    <FontAwesomeIcon icon={faGithub} className='text-lg' />
                  </a>
                </div>

              </div>
              <div className='my-5 text-center'>
                <span>Gemilai adaptation with</span>
                <span className='mx-1'>{randomIcon}</span>
                <span>
                  {' '}
                  by&nbsp;
                  <a
                    className='text-primary hover:text-primary/80 font-medium transition'
                    href='https://github.com/Rico-X/GemilaiMate'
                    target='_blank'
                    rel='noreferrer'
                  >
                    Rico-X
                  </a>
                </span>
              </div>
            </>
          )}

          <div>
            <button
              type='button'
              onClick={onToggleCollapsed}
              className={
                collapsed
                  ? 'btn btn-square btn-md text-base-content hover:bg-base-content/10 hover:text-base-content h-12 min-h-0 w-12 min-w-0 rounded-xl border-none bg-transparent px-0'
                  : 'btn btn-md text-base-content hover:text-base-content hover:bg-base-content/10 h-12 w-full justify-start gap-3 border-none bg-transparent px-2'
              }
              aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
              title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            >
              <FontAwesomeIcon
                size='md'
                icon={collapsed ? faCircleChevronRight : faCircleChevronLeft}
              />
              {!collapsed ? (
                <div className='indicator'>
                  <span>Collapse</span>
                </div>
              ) : null}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

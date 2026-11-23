import { useId } from 'react'

/**
 * The FlashPilot mark: a bolt inside a targeting ring.
 * Same artwork as docs/logo_flashpilot.svg, rebuilt as a React component so
 * it stays crisp at any size and can inherit the page's ink background.
 */
export default function Logo({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, '')

  return (
    <svg
      className={className}
      viewBox="0 0 512 512"
      role="img"
      aria-label="FlashPilot"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={`bolt-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FF6B35" />
          <stop offset="50%" stopColor="#F7931E" />
          <stop offset="100%" stopColor="#FFD700" />
        </linearGradient>
        <linearGradient id={`ring-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00D4FF" />
          <stop offset="100%" stopColor="#0099CC" />
        </linearGradient>
      </defs>

      <circle cx="256" cy="256" r="240" fill="#101a30" stroke={`url(#ring-${uid})`} strokeWidth="8" />
      <circle
        cx="256"
        cy="256"
        r="200"
        fill="none"
        stroke={`url(#ring-${uid})`}
        strokeWidth="4"
        strokeDasharray="20 12"
        opacity="0.55"
      />
      <g stroke={`url(#ring-${uid})`} strokeWidth="5" fill="none" opacity="0.6">
        <path d="M100 190 L100 100 L190 100" />
        <path d="M322 100 L412 100 L412 190" />
        <path d="M100 322 L100 412 L190 412" />
        <path d="M322 412 L412 412 L412 322" />
      </g>
      <path
        d="M256 80 L180 240 L240 240 L200 380 L332 200 L272 200 L320 80 Z"
        fill={`url(#bolt-${uid})`}
        stroke="#FF6B35"
        strokeWidth="3"
      />
    </svg>
  )
}

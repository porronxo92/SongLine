import clsx from 'clsx';
import { useId } from 'react';

/** Ficha de objeción: púa de guitarra con una nota. `spent` la deja como contorno discontinuo. */
export function Pick({
  spent = false,
  width = 44,
  className,
}: {
  spent?: boolean;
  width?: number;
  className?: string;
}) {
  const id = useId();
  const height = Math.round((width * 52) / 44);
  return (
    <svg
      viewBox="0 0 40 48"
      width={width}
      height={height}
      aria-hidden="true"
      className={clsx('pick', spent && 'spent', className)}
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFD166" />
          <stop offset="1" stopColor="#FFB703" />
        </linearGradient>
      </defs>
      {spent ? (
        <path
          d="M20 46S3 30 3 16C3 7 10 2 20 2s17 5 17 14c0 14-17 30-17 30Z"
          fill="none"
          stroke="#6C72A8"
          strokeWidth="2.5"
          strokeDasharray="4 4"
        />
      ) : (
        <>
          <path
            d="M20 46S3 30 3 16C3 7 10 2 20 2s17 5 17 14c0 14-17 30-17 30Z"
            fill={`url(#${id})`}
            stroke="#C98700"
            strokeWidth="2"
          />
          <path d="M11 14c2-4 6-6 10-6" stroke="#fff" strokeOpacity=".6" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <path
            d="M17 31V19l8-2v10"
            stroke="#0D0E15"
            strokeOpacity=".75"
            strokeWidth="2.4"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="15" cy="31" r="2.4" fill="#0D0E15" fillOpacity=".75" />
          <circle cx="23" cy="27" r="2.4" fill="#0D0E15" fillOpacity=".75" />
        </>
      )}
    </svg>
  );
}

// Icônes SVG inline (style trait, 24×24) — aucune dépendance externe.
import type { ReactNode, SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...rest }: P & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconDashboard = (p: P) => (
  <Svg {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></Svg>
);
export const IconAccounts = (p: P) => (
  <Svg {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></Svg>
);
export const IconConsole = (p: P) => (
  <Svg {...p}><rect x="9" y="2" width="6" height="11" rx="3" /><path d="M5 10a7 7 0 0 0 14 0" /><path d="M12 17v4" /><path d="M8 21h8" /></Svg>
);
export const IconKey = (p: P) => (
  <Svg {...p}><circle cx="7.5" cy="15.5" r="4.5" /><path d="m10.7 12.3 9.3-9.3" /><path d="m17 5 3 3" /><path d="m14 8 2 2" /></Svg>
);
export const IconForm = (p: P) => (
  <Svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h8" /><path d="M8 17h5" /></Svg>
);
export const IconPlus = (p: P) => (<Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>);
export const IconTrash = (p: P) => (<Svg {...p}><path d="M3 6h18" /><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /></Svg>);
export const IconCopy = (p: P) => (<Svg {...p}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></Svg>);
export const IconLogout = (p: P) => (<Svg {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></Svg>);
export const IconCheck = (p: P) => (<Svg {...p}><path d="M20 6 9 17l-5-5" /></Svg>);
export const IconX = (p: P) => (<Svg {...p}><path d="M18 6 6 18M6 6l12 12" /></Svg>);
export const IconChevronRight = (p: P) => (<Svg {...p}><path d="m9 18 6-6-6-6" /></Svg>);
export const IconArrowLeft = (p: P) => (<Svg {...p}><path d="m12 19-7-7 7-7" /><path d="M19 12H5" /></Svg>);
export const IconLock = (p: P) => (<Svg {...p}><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></Svg>);
export const IconWave = (p: P) => (<Svg {...p}><path d="M2 12h2M6 8v8M10 4v16M14 7v10M18 9v6M22 12h-2" /></Svg>);
export const IconAlert = (p: P) => (<Svg {...p}><path d="m21.7 18-9-15a1 1 0 0 0-1.7 0l-9 15A1 1 0 0 0 3 19.5h18a1 1 0 0 0 .7-1.5Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></Svg>);
export const IconPlay = (p: P) => (<Svg {...p}><path d="m6 3 14 9-14 9V3z" /></Svg>);
export const IconStop = (p: P) => (<Svg {...p}><rect x="5" y="5" width="14" height="14" rx="2" /></Svg>);
export const IconSkip = (p: P) => (<Svg {...p}><path d="m5 4 10 8-10 8V4z" /><path d="M19 5v14" /></Svg>);
export const IconGlobe = (p: P) => (<Svg {...p}><circle cx="12" cy="12" r="10" /><path d="M2 12h20" /><path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20Z" /></Svg>);

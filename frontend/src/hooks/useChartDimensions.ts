import { useCallback, useEffect, useRef, useState } from "react";

export interface Dimensions {
  width: number;
  height: number;
  marginTop: number;
  marginRight: number;
  marginBottom: number;
  marginLeft: number;
  innerWidth: number;
  innerHeight: number;
}

const DEFAULT_MARGINS = {
  marginTop: 20,
  marginRight: 20,
  marginBottom: 40,
  marginLeft: 50,
};

export function useChartDimensions(
  margins = DEFAULT_MARGINS,
): [React.RefCallback<HTMLDivElement>, Dimensions, HTMLDivElement | null] {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(600);
  const [height, setHeight] = useState(300);
  const obsRef = useRef<ResizeObserver | null>(null);

  const ref = useCallback((el: HTMLDivElement | null) => {
    if (obsRef.current) {
      obsRef.current.disconnect();
      obsRef.current = null;
    }
    if (el) {
      const obs = new ResizeObserver(([entry]) => {
        setWidth(entry.contentRect.width);
        setHeight(entry.contentRect.height);
      });
      obs.observe(el);
      obsRef.current = obs;
    }
    setNode(el);
  }, []);

  useEffect(() => {
    return () => {
      obsRef.current?.disconnect();
    };
  }, []);

  const dims: Dimensions = {
    ...margins,
    width,
    height,
    innerWidth: Math.max(0, width - margins.marginLeft - margins.marginRight),
    innerHeight: Math.max(0, height - margins.marginTop - margins.marginBottom),
  };

  return [ref, dims, node];
}

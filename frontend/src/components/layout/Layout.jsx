import { Outlet, useSearchParams } from "react-router";
import Nav from "./Nav";

/*
 * Marco de la aplicación. Con ?figura=1 se oculta la navegación y el
 * contenido queda a ancho fijo, listo para capturar como figura.
 */
export default function Layout() {
  const [params] = useSearchParams();
  const figura = params.get("figura") === "1";

  if (figura) {
    return (
      <div className="min-h-screen bg-white text-slate-900">
        <main className="mx-auto w-[1040px] px-8 py-8">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 md:flex">
      <Nav />
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default function Steps({ current, total }) {
  return (
    <div className="steps" aria-label={`Paso ${current} de ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i + 1 < current ? "done" : i + 1 === current ? "active" : ""} />
      ))}
    </div>
  );
}

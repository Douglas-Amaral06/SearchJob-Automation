import JobCard from "./JobCard";

export default function JobList({ vagas, onMarcarCandidatado, onRemoverCandidatura }) {
  if (!vagas || vagas.length === 0) {
    return null;
  }

  return (
    <div className="w-full max-w-4xl mt-8 space-y-4">
      {vagas.map((vaga, index) => (
        <JobCard
          key={`${vaga.url_candidatura}-${index}`}
          vaga={vaga}
          onMarcarCandidatado={onMarcarCandidatado}
          onRemoverCandidatura={onRemoverCandidatura}
        />
      ))}
    </div>
  );
}
import React, { useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckSquare,
  Clock,
  FileImage,
  FileText,
  Library,
  Loader2,
  Microscope,
  Plus,
  Sparkles,
  Square,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { Project, ProjectType, PendingProjectAsset } from '../types';
import { useDeleteProject } from '../hooks/useProjects';
import { useToastStore } from '../stores/toastStore';

interface DashboardProps {
  projects: Project[];
  onCreateProject: (
    title: string,
    type: ProjectType,
    description: string,
    methodology?: string,
    findings?: string,
    initialAssets?: PendingProjectAsset[]
  ) => Promise<void> | void;
  onCreateProjectFromReview: (
    sourceProjectId: string,
    targetType?: ProjectType,
    openAfterCreate?: boolean
  ) => Promise<unknown> | void;
  onOpenProject: (projectId: string) => void;
}

const getTheme = (type: ProjectType) => {
  if (type === ProjectType.LIT_REVIEW) return { icon: 'bg-indigo-100 text-indigo-600', badge: 'bg-indigo-100 text-indigo-700', button: 'bg-indigo-600 hover:bg-indigo-500', label: 'Literature Review' };
  if (type === ProjectType.EXPERIMENTAL) return { icon: 'bg-emerald-100 text-emerald-600', badge: 'bg-emerald-100 text-emerald-700', button: 'bg-emerald-600 hover:bg-emerald-500', label: 'Research Paper' };
  return { icon: 'bg-purple-100 text-purple-600', badge: 'bg-purple-100 text-purple-700', button: 'bg-purple-600 hover:bg-purple-500', label: 'Manuscript' };
};

export const Dashboard: React.FC<DashboardProps> = ({
  projects,
  onCreateProject,
  onCreateProjectFromReview,
  onOpenProject,
}) => {
  const deleteProject = useDeleteProject();
  const { addToast } = useToastStore();

  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [showReviewWorkflowModal, setShowReviewWorkflowModal] = useState(false);
  const [selectedType, setSelectedType] = useState<ProjectType>(ProjectType.LIT_REVIEW);
  const [reviewTargetType, setReviewTargetType] = useState<ProjectType>(ProjectType.EXPERIMENTAL);
  const [reviewSourceIds, setReviewSourceIds] = useState<string[]>([]);
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const [isCreatingFromReview, setIsCreatingFromReview] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const [step, setStep] = useState(1);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [methodology, setMethodology] = useState('');
  const [findings, setFindings] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<PendingProjectAsset[]>([]);

  const sortedProjects = [...projects].sort((a, b) => {
    const aTime = a.lastModified instanceof Date ? a.lastModified.getTime() : 0;
    const bTime = b.lastModified instanceof Date ? b.lastModified.getTime() : 0;
    return bTime - aTime;
  });
  const litReviewProjects = sortedProjects.filter((project) => project.type === ProjectType.LIT_REVIEW);
  const selectedProjects = sortedProjects.filter((project) => selectedProjectIds.has(project.id));
  const selectedLitReviews = selectedProjects.filter((project) => project.type === ProjectType.LIT_REVIEW);
  const allSelected = sortedProjects.length > 0 && selectedProjectIds.size === sortedProjects.length;

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setMethodology('');
    setFindings('');
    setUploadedFiles([]);
    setStep(1);
  };

  const openNewProjectModal = (type: ProjectType) => {
    setSelectedType(type);
    setStep(1);
    setShowNewProjectModal(true);
  };

  const openReviewWorkflow = (ids?: string[]) => {
    if (litReviewProjects.length === 0) {
      openNewProjectModal(ProjectType.LIT_REVIEW);
      return;
    }
    setReviewSourceIds(ids && ids.length > 0 ? ids : [litReviewProjects[0].id]);
    setReviewTargetType(ProjectType.EXPERIMENTAL);
    setShowReviewWorkflowModal(true);
  };

  const handleCreate = async () => {
    if (!title) return;

    const assets: PendingProjectAsset[] = uploadedFiles.map((file) => ({
      ...file,
      kind: file.kind || (selectedType === ProjectType.EXPERIMENTAL ? 'research' : 'lab'),
      description: file.description || 'Uploaded during project setup for drafting support.',
      methodologyNote: file.methodologyNote || methodology || undefined,
      sectionHint: file.sectionHint || (file.type === 'image' ? 'results' : 'methodology'),
    }));

    try {
      await onCreateProject(title, selectedType, description, methodology, findings, assets);
      setShowNewProjectModal(false);
      resetForm();
    } catch (error) {
      console.error(error);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const file = e.target.files[0];
    const type = file.type.includes('image') ? 'image' : 'data';
    setUploadedFiles((prev) => [
      ...prev,
      { name: file.name, type, file, kind: selectedType === ProjectType.EXPERIMENTAL ? 'research' : 'lab' },
    ]);
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) return;
    try {
      await deleteProject.mutateAsync(projectId);
      setSelectedProjectIds((prev) => {
        const next = new Set(prev);
        next.delete(projectId);
        return next;
      });
      addToast('Project deleted successfully', 'success');
    } catch (error) {
      console.error(error);
      addToast('Failed to delete project', 'error');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedProjectIds.size === 0) return;
    if (!window.confirm(`Delete ${selectedProjectIds.size} selected project(s)? This action cannot be undone.`)) return;

    setIsBulkDeleting(true);
    const results = await Promise.allSettled(Array.from(selectedProjectIds).map((id) => deleteProject.mutateAsync(id)));
    const failed = results.filter((result) => result.status === 'rejected').length;
    const succeeded = results.length - failed;
    if (succeeded > 0) addToast(`Deleted ${succeeded} project${succeeded === 1 ? '' : 's'}.`, 'success');
    if (failed > 0) addToast(`${failed} project${failed === 1 ? '' : 's'} could not be deleted.`, 'warning');
    setSelectedProjectIds(new Set());
    setIsBulkDeleting(false);
  };

  const handleReviewWorkflowSubmit = async () => {
    if (reviewSourceIds.length === 0) return;
    setIsCreatingFromReview(true);
    try {
      const openAfterCreate = reviewSourceIds.length === 1;
      if (openAfterCreate) {
        await onCreateProjectFromReview(reviewSourceIds[0], reviewTargetType, true);
      } else {
        const results = await Promise.allSettled(
          reviewSourceIds.map((reviewId) => onCreateProjectFromReview(reviewId, reviewTargetType, false))
        );
        const failed = results.filter((result) => result.status === 'rejected').length;
        const succeeded = results.length - failed;
        if (succeeded > 0) {
          addToast(`Created ${succeeded} writing workspace${succeeded === 1 ? '' : 's'}.`, 'success');
        }
        if (failed > 0) {
          addToast(`${failed} review conversion${failed === 1 ? '' : 's'} failed.`, 'warning');
        }
        setSelectedProjectIds(new Set());
        setShowReviewWorkflowModal(false);
        setReviewSourceIds([]);
        return;
      }
      addToast('Writing workspace created from literature review.', 'success');
      setSelectedProjectIds(new Set());
      setShowReviewWorkflowModal(false);
      setReviewSourceIds([]);
    } catch (error) {
      console.error(error);
      addToast('Failed to create writing workspace from the selected review.', 'error');
    } finally {
      setIsCreatingFromReview(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 overflow-y-auto">
      <div className="max-w-6xl mx-auto">
        <header className="mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 tracking-tight">Welcome back, Jane.</h1>
          <p className="text-gray-500">Start with discovery, then branch your literature review into your own paper workspace when you are ready to write.</p>
        </header>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Projects</div>
            <div className="text-3xl font-bold text-gray-900">{sortedProjects.length}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Literature Reviews</div>
            <div className="text-3xl font-bold text-indigo-700">{litReviewProjects.length}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Writing Workspaces</div>
            <div className="text-3xl font-bold text-emerald-700">{sortedProjects.filter((project) => project.type !== ProjectType.LIT_REVIEW).length}</div>
          </div>
        </section>

        <section className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Start New</h2>
            <div className="text-xs text-gray-500">Recommended flow: Literature Review {'->'} Research Paper from Review</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            <button onClick={() => openNewProjectModal(ProjectType.LIT_REVIEW)} className="group text-left bg-white p-6 rounded-xl border border-gray-200 hover:border-indigo-400 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-indigo-50 rounded-lg flex items-center justify-center mb-4 group-hover:bg-indigo-600 transition-colors"><BookOpen className="w-6 h-6 text-indigo-600 group-hover:text-white transition-colors" /></div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">Literature Review</h3>
              <p className="text-sm text-gray-500 mb-4">Start with discovery, paper collection, and evidence mapping.</p>
              <div className="flex items-center text-xs font-semibold text-indigo-600">Start Discovery <ArrowRight className="w-3 h-3 ml-1" /></div>
            </button>

            <button onClick={() => openReviewWorkflow()} className="group text-left bg-white p-6 rounded-xl border border-gray-200 hover:border-emerald-400 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-emerald-50 rounded-lg flex items-center justify-center mb-4 group-hover:bg-emerald-600 transition-colors"><Sparkles className="w-6 h-6 text-emerald-600 group-hover:text-white transition-colors" /></div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">Research Paper from Review</h3>
              <p className="text-sm text-gray-500 mb-4">Reuse an existing literature review as the starting library for your own paper.</p>
              <div className="flex items-center text-xs font-semibold text-emerald-600">{litReviewProjects.length > 0 ? 'Choose Review Project' : 'Create a Review First'} <ArrowRight className="w-3 h-3 ml-1" /></div>
            </button>

            <button onClick={() => openNewProjectModal(ProjectType.EXPERIMENTAL)} className="group text-left bg-white p-6 rounded-xl border border-gray-200 hover:border-emerald-400 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-emerald-50 rounded-lg flex items-center justify-center mb-4 group-hover:bg-emerald-600 transition-colors"><Upload className="w-6 h-6 text-emerald-600 group-hover:text-white transition-colors" /></div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">Experimental Paper</h3>
              <p className="text-sm text-gray-500 mb-4">Start with your own methods, figures, and findings.</p>
              <div className="flex items-center text-xs font-semibold text-emerald-600">Upload & Draft <ArrowRight className="w-3 h-3 ml-1" /></div>
            </button>

            <button onClick={() => openNewProjectModal(ProjectType.MANUSCRIPT)} className="group text-left bg-white p-6 rounded-xl border border-gray-200 hover:border-purple-400 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center mb-4 group-hover:bg-purple-600 transition-colors"><FileText className="w-6 h-6 text-purple-600 group-hover:text-white transition-colors" /></div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">General Manuscript</h3>
              <p className="text-sm text-gray-500 mb-4">Open a writing-first workspace for flexible drafting.</p>
              <div className="flex items-center text-xs font-semibold text-purple-600">Open Studio <ArrowRight className="w-3 h-3 ml-1" /></div>
            </button>
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Recent Work</h2>
              <p className="text-xs text-gray-500 mt-1">Use bulk actions to clean up projects or branch selected reviews into writing workspaces.</p>
            </div>
            {sortedProjects.length > 0 && (
              <button onClick={() => setSelectedProjectIds(allSelected ? new Set() : new Set(sortedProjects.map((project) => project.id)))} className="text-xs font-medium text-gray-500 hover:text-indigo-600 flex items-center gap-2">
                {allSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                {allSelected ? 'Clear Selection' : 'Select All'}
              </button>
            )}
          </div>

          {selectedProjectIds.size > 0 && (
            <div className="mb-4 bg-white rounded-xl border border-gray-200 p-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">{selectedProjectIds.size} project{selectedProjectIds.size === 1 ? '' : 's'} selected</div>
                <div className="text-xs text-gray-500 mt-1">Branch selected reviews into paper workspaces, or delete projects in bulk.</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedLitReviews.length > 0 && (
                  <button onClick={() => openReviewWorkflow(selectedLitReviews.map((project) => project.id))} className="px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100">
                    Start Paper from Selected Reviews
                  </button>
                )}
                <button onClick={handleBulkDelete} disabled={isBulkDeleting} className="px-3 py-2 text-xs font-semibold rounded-lg bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 flex items-center gap-2">
                  {isBulkDeleting && <Loader2 className="w-3 h-3 animate-spin" />}
                  Delete Selected
                </button>
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {sortedProjects.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">No projects yet. Start one above.</div>
            ) : (
              <div className="divide-y divide-gray-100">
                {sortedProjects.map((project) => {
                  const theme = getTheme(project.type);
                  const isSelected = selectedProjectIds.has(project.id);
                  return (
                    <div key={project.id} className={`p-4 transition-colors ${isSelected ? 'bg-indigo-50/40' : 'hover:bg-gray-50'}`}>
                      <div className="flex items-start gap-4">
                        <button onClick={() => setSelectedProjectIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(project.id)) next.delete(project.id);
                          else next.add(project.id);
                          return next;
                        })} className="mt-1 text-gray-400 hover:text-indigo-600">
                          {isSelected ? <CheckSquare className="w-5 h-5 text-indigo-600" /> : <Square className="w-5 h-5" />}
                        </button>

                        <div onClick={() => onOpenProject(project.id)} className="flex items-start gap-4 cursor-pointer flex-1 min-w-0">
                          <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${theme.icon}`}>
                            {project.type === ProjectType.LIT_REVIEW && <BookOpen className="w-5 h-5" />}
                            {project.type === ProjectType.EXPERIMENTAL && <Microscope className="w-5 h-5" />}
                            {project.type === ProjectType.MANUSCRIPT && <FileText className="w-5 h-5" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                              <h4 className="font-semibold text-gray-900 truncate">{project.title}</h4>
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${theme.badge}`}>{theme.label}</span>
                            </div>
                            <p className="text-xs text-gray-500 line-clamp-2">{project.description || 'No description yet.'}</p>
                            <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
                              <div className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{project.lastModified instanceof Date && !isNaN(project.lastModified.getTime()) ? project.lastModified.toLocaleDateString() : 'Just now'}</div>
                              <div>{project.wordCount} words</div>
                              <div>{project.papers.length} papers</div>
                              <div>{project.assets.length} assets</div>
                            </div>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-end gap-2">
                          {project.type === ProjectType.LIT_REVIEW ? (
                            <>
                              <button onClick={() => openReviewWorkflow([project.id])} className="px-3 py-1.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded text-xs font-medium flex items-center gap-1">
                                <Sparkles className="w-3 h-3" /> Start Paper
                              </button>
                              <button onClick={() => onOpenProject(project.id)} className="px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-medium flex items-center gap-1">
                                <BookOpen className="w-3 h-3" /> Open Review
                              </button>
                            </>
                          ) : (
                            <button onClick={() => onOpenProject(project.id)} className="px-3 py-1.5 bg-gray-900 text-white hover:bg-gray-800 rounded text-xs font-medium flex items-center gap-1">
                              <FileText className="w-3 h-3" /> Open Studio
                            </button>
                          )}
                          <button onClick={() => handleDeleteProject(project.id)} className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded" title="Delete project">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>

      {showNewProjectModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  {selectedType === ProjectType.LIT_REVIEW && <BookOpen className="w-5 h-5 text-indigo-600" />}
                  {selectedType === ProjectType.EXPERIMENTAL && <Microscope className="w-5 h-5 text-emerald-600" />}
                  {selectedType === ProjectType.MANUSCRIPT && <Sparkles className="w-5 h-5 text-purple-600" />}
                  {selectedType === ProjectType.LIT_REVIEW && 'New Literature Review'}
                  {selectedType === ProjectType.EXPERIMENTAL && 'New Experimental Paper'}
                  {selectedType === ProjectType.MANUSCRIPT && 'New Manuscript'}
                </h3>
                <div className="text-sm text-gray-500 mt-1">Step {step} of {selectedType === ProjectType.EXPERIMENTAL ? 2 : 1}</div>
              </div>
              <button onClick={() => setShowNewProjectModal(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>

            <div className="p-6">
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Project Title</label>
                    <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 outline-none" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Description / Goal</label>
                    <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 h-32 resize-none outline-none" />
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Methodology / Protocol</label>
                      <textarea value={methodology} onChange={(e) => setMethodology(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 h-40 resize-none outline-none text-sm" />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">Key Findings</label>
                      <textarea value={findings} onChange={(e) => setFindings(e.target.value)} className="w-full border border-gray-300 rounded-lg px-4 py-2 h-40 resize-none outline-none text-sm" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 uppercase mb-2">Upload Results & Figures</label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 flex flex-col items-center justify-center bg-gray-50 relative">
                      <input type="file" className="absolute inset-0 opacity-0 cursor-pointer" onChange={handleFileUpload} />
                      <Upload className="w-8 h-8 text-gray-400 mb-2" />
                      <span className="text-sm text-gray-500">Drop charts (PNG) or data (CSV) here</span>
                    </div>
                    {uploadedFiles.length > 0 && (
                      <div className="mt-4 space-y-2">
                        {uploadedFiles.map((file, index) => (
                          <div key={`${file.name}-${index}`} className="flex items-center justify-between p-2 bg-white border border-gray-200 rounded-md text-sm">
                            <div className="flex items-center gap-2"><FileImage className="w-4 h-4 text-emerald-500" /><span>{file.name}</span></div>
                            <Check className="w-4 h-4 text-green-500" />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-between items-center">
              <button onClick={() => setShowNewProjectModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors">Cancel</button>
              <div className="flex gap-2">
                {step === 2 && <button onClick={() => setStep(1)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors">Back</button>}
                {selectedType === ProjectType.EXPERIMENTAL && step === 1 ? (
                  <button onClick={() => setStep(2)} disabled={!title} className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-2">Next <ArrowRight className="w-4 h-4" /></button>
                ) : (
                  <button onClick={handleCreate} disabled={!title} className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2 ${getTheme(selectedType).button}`}><Plus className="w-4 h-4" /> Create Project</button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {showReviewWorkflowModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2"><Library className="w-5 h-5 text-emerald-600" /> Start Writing from a Literature Review</h3>
                <div className="text-sm text-gray-500 mt-1">Keep your review project for discovery, then branch it into a writing workspace with the same paper library.</div>
              </div>
              <button onClick={() => setShowReviewWorkflowModal(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-3">Choose Review Projects</label>
                <div className="border border-gray-200 rounded-xl divide-y divide-gray-100 max-h-64 overflow-y-auto">
                  {litReviewProjects.map((project) => {
                    const selected = reviewSourceIds.includes(project.id);
                    return (
                      <button key={project.id} onClick={() => setReviewSourceIds((prev) => prev.includes(project.id) ? prev.filter((id) => id !== project.id) : [...prev, project.id])} className={`w-full text-left px-4 py-3 flex items-start gap-3 ${selected ? 'bg-emerald-50' : 'hover:bg-gray-50'}`}>
                        <div className="pt-0.5">{selected ? <CheckSquare className="w-5 h-5 text-emerald-600" /> : <Square className="w-5 h-5 text-gray-400" />}</div>
                        <div className="min-w-0">
                          <div className="font-semibold text-gray-900">{project.title}</div>
                          <div className="text-xs text-gray-500 mt-1 line-clamp-2">{project.description || 'No description yet.'}</div>
                          <div className="text-[11px] text-gray-400 mt-2">{project.papers.length} papers · {project.wordCount} words</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button onClick={() => setReviewTargetType(ProjectType.EXPERIMENTAL)} className={`rounded-xl border p-4 text-left ${reviewTargetType === ProjectType.EXPERIMENTAL ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200'}`}>
                  <div className="font-semibold text-gray-900 mb-1">Research Paper</div>
                  <div className="text-sm text-gray-500">Recommended for your own study write-up, methods/results drafting, and later asset-driven sections.</div>
                </button>
                <button onClick={() => setReviewTargetType(ProjectType.MANUSCRIPT)} className={`rounded-xl border p-4 text-left ${reviewTargetType === ProjectType.MANUSCRIPT ? 'border-purple-500 bg-purple-50' : 'border-gray-200'}`}>
                  <div className="font-semibold text-gray-900 mb-1">Manuscript</div>
                  <div className="text-sm text-gray-500">Best for writing-first workspaces, proposals, or lighter-weight paper drafting.</div>
                </button>
              </div>
            </div>

            <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-between items-center">
              <button onClick={() => setShowReviewWorkflowModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors">Cancel</button>
              <button onClick={handleReviewWorkflowSubmit} disabled={reviewSourceIds.length === 0 || isCreatingFromReview} className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2 ${getTheme(reviewTargetType).button}`}>
                {isCreatingFromReview && <Loader2 className="w-4 h-4 animate-spin" />}
                {reviewSourceIds.length > 1 ? `Create ${reviewSourceIds.length} Workspaces` : 'Create Writing Workspace'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

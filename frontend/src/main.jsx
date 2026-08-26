import React, { useEffect, useState, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import cytoscape from 'cytoscape';
import {
  Upload,
  Network,
  FileText,
  Sparkles,
  X,
  ChevronRight,
  ChevronLeft,
  ZoomIn,
  ZoomOut,
  Edit3,
  Trash2,
  Copy,
  Pin,
  Plus,
  Send,
  Sliders,
  Scale,
  Sun,
  Moon,
  Monitor,
  Lightbulb,
  CornerDownRight,
  Save,
  Home,
  MessageSquare,
  MoreVertical,
  Search,
  File,
  Hash
} from 'lucide-react';
import './index.css';

const API = 'http://localhost:8000/api';

const isValidDocumentId = (value) =>
  typeof value === 'string' &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value.trim());

const analyzeDocument = async (documentId) => {
  console.log('[ANALYZE DEBUG]', {
    documentId,
    type: typeof documentId,
    isArray: Array.isArray(documentId)
  });

  if (!isValidDocumentId(documentId)) {
    throw new Error(
      `Invalid document ID for analysis: ${JSON.stringify(documentId)}`
    );
  }

  const id = documentId.trim();
  const url = `${API}/analyze/${encodeURIComponent(id)}`;

  console.log('[ANALYZE REQUEST]', url);

  const response = await fetch(url, {
    method: 'POST',
    signal: AbortSignal.timeout(120000)
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `Analysis failed (${response.status}): ${text || response.statusText}`
    );
  }

  return await response.json();
};

const NODE_COLORS = {
  PAPER: '#0f172a',
  RESEARCHER: '#4f46e5',
  DEPARTMENT: '#d97706',
  DATASET: '#ea580c',
  METHOD: '#2563eb',
  TOPIC: '#0284c7',
  TECHNOLOGY: '#64748b',
  NOTE: '#10b981'
};

import DOMPurify from 'dompurify';

function MarkdownViewer({ content, onWikilinkClick }) {
  if (!content) return null;

  try {
    content = DOMPurify.sanitize(content, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
  } catch (e) {
    content = String(content).replace(/<[^>]*>/g, '');
  }

  const renderFormattedText = (text) => {
    const parts = text.split(/(\[\[.*?\]\])/g);
    return parts.map((part, idx) => {
      if (part.startsWith('[[') && part.endsWith(']]')) {
        const linkText = part.slice(2, -2);
        return (
          <span
            key={idx}
            onClick={() => onWikilinkClick && onWikilinkClick(linkText)}
            className="wikilink-badge mx-0.5"
            title={`Explore: ${linkText}`}
          >
            {linkText}
          </span>
        );
      }
      const boldParts = part.split(/(\*\*.*?\*\*)/g);
      return boldParts.map((bpart, bidx) => {
        if (bpart.startsWith('**') && bpart.endsWith('**')) {
          return <strong key={bidx} className="font-semibold">{bpart.slice(2, -2)}</strong>;
        }
        const codeParts = bpart.split(/(`.*?`)/g);
        return codeParts.map((cpart, cidx) => {
          if (cpart.startsWith('`') && cpart.endsWith('`')) {
            return <code key={cidx} className="px-1.5 py-0.5 rounded text-[11px] bg-slate-100 dark:bg-slate-800 font-mono">{cpart.slice(1, -1)}</code>;
          }
          return cpart;
        });
      });
    });
  };

  const lines = content.split('\n');
  const elements = [];
  let inTable = false;
  let tableRows = [];

  const flushTable = () => {
    if (tableRows.length > 0) {
      elements.push(
        <div key={`table-${elements.length}`} className="overflow-x-auto my-3">
          <table className="min-w-full text-[11px]">
            <thead>
              <tr>
                {tableRows[0].map((cell, cidx) => (
                  <th key={cidx} className="p-2 border border-slate-200 dark:border-slate-700 font-semibold text-left">{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, ridx) => (
                <tr key={ridx}>
                  {row.map((cell, cidx) => (
                    <td key={cidx} className="p-2 border border-slate-200 dark:border-slate-700">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    }
    inTable = false;
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (trimmed.includes('---')) return;
      inTable = true;
      const cells = trimmed.split('|').slice(1, -1).map(c => renderFormattedText(c.trim()));
      tableRows.push(cells);
      return;
    } else if (inTable) {
      flushTable();
    }

    if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={idx} className="text-lg font-bold mt-4 mb-2">{renderFormattedText(trimmed.slice(2))}</h1>);
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={idx} className="text-[15px] font-bold mt-3 mb-1.5">{renderFormattedText(trimmed.slice(3))}</h2>);
    } else if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={idx} className="text-[13px] font-bold mt-2.5 mb-1">{renderFormattedText(trimmed.slice(4))}</h3>);
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <li key={idx} className="ml-4 list-disc my-0.5 text-[12px] text-slate-600 dark:text-slate-400">
          {renderFormattedText(trimmed.slice(2))}
        </li>
      );
    } else if (/^\d+\.\s/.test(trimmed)) {
      const textAfterNum = trimmed.replace(/^\d+\.\s/, '');
      elements.push(
        <li key={idx} className="ml-4 list-decimal my-0.5 text-[12px] text-slate-600 dark:text-slate-400">
          {renderFormattedText(textAfterNum)}
        </li>
      );
    } else if (trimmed === '---') {
      elements.push(<hr key={idx} className="my-3 border-slate-200 dark:border-slate-700" />);
    } else if (trimmed.length > 0) {
      elements.push(<p key={idx} className="my-1.5 text-[12px] text-slate-600 dark:text-slate-400 leading-relaxed">{renderFormattedText(trimmed)}</p>);
    }
  });

  if (inTable) flushTable();

  return <div className="prose-academic">{elements}</div>;
}

function KnowledgeGraphView({ data, selectedType, onSelectNode, focusNodeId, isDark }) {
  const cyRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !data.nodes || data.nodes.length === 0) return;

    const filteredNodes = selectedType && selectedType !== 'ALL'
      ? data.nodes.filter(n => n.type === selectedType)
      : data.nodes;

    const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredEdges = (data.edges || []).filter(e => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));

    const elements = [
      ...filteredNodes.map(n => ({
        data: { id: n.id, label: n.label, type: n.type, description: n.description, degree: n.degree || 1 }
      })),
      ...filteredEdges.map(e => ({
        data: { id: e.id, source: e.source, target: e.target, label: e.label, confidence: e.confidence }
      }))
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'background-color': '#475569',
            'color': isDark ? '#f1f5f9' : '#0f172a',
            'font-size': '10px',
            'font-weight': 600,
            'font-family': 'Plus Jakarta Sans, Inter, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-wrap': 'wrap',
            'text-max-width': '100px',
            'width': 'mapData(degree, 1, 10, 20, 36)',
            'height': 'mapData(degree, 1, 10, 20, 36)',
            'border-width': 2,
            'border-color': isDark ? '#1e293b' : '#ffffff',
            'transition-property': 'opacity, border-width, border-color',
            'transition-duration': '0.2s'
          }
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.5,
            'line-color': isDark ? '#334155' : '#e2e8f0',
            'target-arrow-color': isDark ? '#475569' : '#cbd5e1',
            'width': 1,
            'opacity': 0.7
          }
        },
        { selector: 'node[type="PAPER"]', style: { 'background-color': isDark ? '#e2e8f0' : NODE_COLORS.PAPER, 'color': isDark ? '#ffffff' : '#0f172a' } },
        { selector: 'node[type="RESEARCHER"]', style: { 'background-color': NODE_COLORS.RESEARCHER } },
        { selector: 'node[type="DEPARTMENT"]', style: { 'background-color': NODE_COLORS.DEPARTMENT } },
        { selector: 'node[type="DATASET"]', style: { 'background-color': NODE_COLORS.DATASET, 'width': 30, 'height': 30 } },
        { selector: 'node[type="METHOD"]', style: { 'background-color': NODE_COLORS.METHOD } },
        { selector: 'node[type="TOPIC"]', style: { 'background-color': NODE_COLORS.TOPIC } },
        { selector: 'node[type="TECHNOLOGY"]', style: { 'background-color': NODE_COLORS.TECHNOLOGY } },
        { selector: 'node[type="NOTE"]', style: { 'background-color': NODE_COLORS.NOTE, 'shape': 'hexagon', 'width': 28, 'height': 28 } },
        { selector: 'node.highlighted', style: { 'border-width': 3, 'border-color': '#6366f1', 'opacity': 1, 'z-index': 999 } },
        { selector: 'node.dimmed', style: { 'opacity': 0.12 } },
        { selector: 'edge.highlighted', style: { 'line-color': '#6366f1', 'target-arrow-color': '#6366f1', 'width': 2.5, 'opacity': 1, 'z-index': 999 } },
        { selector: 'edge.dimmed', style: { 'opacity': 0.06 } }
      ],
      layout: { name: 'cose', animate: true, animationDuration: 600, nodeRepulsion: 5500, idealEdgeLength: 65, edgeElasticity: 100, gravity: 0.3, padding: 30 }
    });

    cy.on('tap', (e) => {
      if (e.target === cy) {
        cy.elements().removeClass('highlighted dimmed');
        onSelectNode(null);
      } else if (e.target.isNode()) {
        const node = e.target;
        const neighborhood = node.closedNeighborhood();
        cy.elements().removeClass('highlighted dimmed');
        cy.elements().addClass('dimmed');
        neighborhood.removeClass('dimmed').addClass('highlighted');
        onSelectNode(node.data());
      }
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [data, selectedType, isDark]);

  useEffect(() => {
    if (!cyRef.current || !focusNodeId) return;
    const target = cyRef.current.getElementById(focusNodeId);
    if (target && target.length > 0) {
      cyRef.current.animate({ center: { eles: target }, zoom: 1.6, duration: 500 });
      const neighborhood = target.closedNeighborhood();
      cyRef.current.elements().removeClass('highlighted dimmed');
      cyRef.current.elements().addClass('dimmed');
      neighborhood.removeClass('dimmed').addClass('highlighted');
      onSelectNode(target.data());
    }
  }, [focusNodeId]);

  return (
    <div className="relative w-full h-full rounded-xl theme-bg-surface border theme-border overflow-hidden">
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
      <div className="absolute top-3 right-3 flex items-center gap-0.5 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm p-0.5 rounded-lg border theme-border shadow-sm">
        <button onClick={() => cyRef.current?.animate({ zoom: cyRef.current.zoom() * 1.25, duration: 200 })} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md" title="Zoom in">
          <ZoomIn size={14} />
        </button>
        <button onClick={() => cyRef.current?.animate({ zoom: cyRef.current.zoom() * 0.8, duration: 200 })} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md" title="Zoom out">
          <ZoomOut size={14} />
        </button>
        <div className="w-px h-3.5 bg-slate-200 dark:bg-slate-700 mx-0.5" />
        <button onClick={() => cyRef.current?.animate({ fit: { padding: 30 }, duration: 400 })} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md text-[10px] font-medium px-1.5">Fit</button>
        <button onClick={() => { cyRef.current?.elements().removeClass('highlighted dimmed'); onSelectNode(null); cyRef.current?.animate({ fit: { padding: 30 }, zoom: 1, duration: 400 }); }} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-md text-[10px] font-medium px-1.5">Reset</button>
      </div>
      <div className="absolute bottom-3 left-3">
        <div className="flex flex-wrap items-center gap-2.5 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm px-2.5 py-1 rounded-lg border theme-border text-[10px]">
          {[
            ['Dataset', NODE_COLORS.DATASET],
            ['Paper', isDark ? '#e2e8f0' : NODE_COLORS.PAPER],
            ['Note', NODE_COLORS.NOTE],
            ['Researcher', NODE_COLORS.RESEARCHER],
            ['Method', NODE_COLORS.METHOD]
          ].map(([name, color]) => (
            <div key={name} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-slate-500 dark:text-slate-400">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('rn_theme') || 'light');
  const [activeView, setActiveView] = useState('home');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState({});
  const [documents, setDocuments] = useState([]);
  const [notes, setNotes] = useState([]);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [datasetMatching, setDatasetMatching] = useState({ datasets: [] });
  const [collaborations, setCollaborations] = useState([]);
  const [redundancies, setRedundancies] = useState([]);

  const [mockAiEnabled, setMockAiEnabled] = useState(false);
  const [primaryModel, setPrimaryModel] = useState('');

  useEffect(() => {
    let mounted = true;
    fetch(`${API}/config`).then((r) => r.json()).then((data) => {
      if (!mounted) return;
      setMockAiEnabled(Boolean(data.mock_ai));
      setPrimaryModel(data.model || '');
    }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  const [selectedDocId, setSelectedDocId] = useState(null);
  const [selectedDocData, setSelectedDocData] = useState(null);
  const [docTab, setDocTab] = useState('overview');

  const [selectedNoteId, setSelectedNoteId] = useState(null);
  const [selectedNote, setSelectedNote] = useState(null);
  const [noteEditMode, setNoteEditMode] = useState('split');
  const [noteSaveStatus, setNoteSaveStatus] = useState('saved');
  const noteAutosaveTimer = useRef(null);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiLoadingAction, setAiLoadingAction] = useState('');
  const [aiResult, setAiResult] = useState(null);

  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const [compareDocA, setCompareDocA] = useState('');
  const [compareDocB, setCompareDocB] = useState('');
  const [compareResult, setCompareResult] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const [graphMode, setGraphMode] = useState('global');
  const [graphFilter, setGraphFilter] = useState('ALL');
  const [selectedGraphNode, setSelectedGraphNode] = useState(null);
  const [focusGraphNodeId, setFocusGraphNodeId] = useState(null);

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadStep, setUploadStep] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadDocId, setUploadDocId] = useState(null);
  const [showSaveNoteModal, setShowSaveNoteModal] = useState(false);
  const [saveNoteTarget, setSaveNoteTarget] = useState('new');
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetMode, setResetMode] = useState('demo');

  const [deleteModal, setDeleteModal] = useState({ open: false, type: null, item: null });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [renameModal, setRenameModal] = useState({ open: false, type: null, item: null });
  const [renameValue, setRenameValue] = useState('');
  const [renameLoading, setRenameLoading] = useState(false);
  const [searchModal, setSearchModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState({ documents: [], notes: [], entities: [] });
  const [searchLoading, setSearchLoading] = useState(false);
  const searchInputRef = useRef(null);
  const searchDebounceRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('rn_theme', theme);
    const root = document.documentElement;
    const resolvedTheme = theme === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme;
    root.setAttribute('data-theme', resolvedTheme);
  }, [theme]);

  useEffect(() => () => clearTimeout(noteAutosaveTimer.current), []);

  const refreshAllData = async () => {
    try {
      const [h, s, docs, nts, g, dm, c, r] = await Promise.all([
        fetch(`${API}/health`).then(res => res.json()),
        fetch(`${API}/stats`).then(res => res.json()),
        fetch(`${API}/documents`).then(res => res.json()),
        fetch(`${API}/notes`).then(res => res.json()),
        fetch(`${API}/graph`).then(res => res.json()),
        fetch(`${API}/datasets`).then(res => res.json()),
        fetch(`${API}/collaborations`).then(res => res.json()),
        fetch(`${API}/redundancy`).then(res => res.json())
      ]);
      setHealth(h);
      setStats(s);
      setDocuments(docs);
      setNotes(nts);
      setGraphData(g);
      setDatasetMatching(dm);
      setCollaborations(c);
      setRedundancies(r);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  };

  useEffect(() => { refreshAllData(); }, []);

  useEffect(() => {
    if (!selectedDocId) return;
    fetch(`${API}/documents/${selectedDocId}`)
      .then(res => res.json())
      .then(data => {
        setSelectedDocData(data);
        triggerAiAction('summarize', selectedDocId);
        setChatMessages([{
          role: 'assistant',
          text: `Hello! I am your research assistant for **${data.document?.title}**. Ask me about methodologies, key contributions, limitations, or anything else about this paper.`,
          sources: [data.document?.filename]
        }]);
      })
      .catch(console.error);
  }, [selectedDocId]);

  useEffect(() => {
    if (!selectedNoteId) return;
    fetch(`${API}/notes/${selectedNoteId}`)
      .then(res => res.json())
      .then(data => setSelectedNote(data))
      .catch(console.error);
  }, [selectedNoteId]);

  const triggerAiAction = async (actionType, docId = selectedDocId) => {
    if (!docId) return;
    setAiLoading(true);
    setAiLoadingAction(actionType);
    setDocTab('overview');

    const endpointMap = {
      summarize: '/ai/summarize',
      analyze: '/ai/analyze',
      explain: '/ai/explain',
      methodology: '/ai/methodology',
      ideas: '/ai/research-ideas',
      questions: '/ai/questions',
      generate_note: '/ai/generate-note'
    };

    try {
      const res = await fetch(`${API}${endpointMap[actionType] || '/ai/action'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(endpointMap[actionType]
          ? { document_id: docId }
          : { document_id: docId, action: actionType })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'AI request failed');
      setAiResult(data);
      if (actionType === 'generate_note' && data.title) {
        setNewNoteTitle(data.title);
      }
    } catch (err) {
      console.error(`AI action ${actionType} failed:`, err);
      const msg = err.message || '';
      const friendly = msg.includes('fetch') || msg.includes('Failed to fetch') || msg.includes('NetworkError')
        ? 'AI service is temporarily unavailable. Please try again.'
        : msg;
      setAiResult({
        markdown: `### AI analysis is temporarily unavailable.\n\n${friendly}\n\nPlease try again or select a different action.`,
        provider: 'Error',
        status: 'unavailable',
        error: friendly
      });
    } finally {
      setAiLoading(false);
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, document_ids: selectedDocId ? [selectedDocId] : [] })
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: 'assistant', text: data.response, sources: data.sources }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'assistant', text: 'AI service is temporarily unavailable. Please try again.', sources: [] }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleSaveAiToNote = async () => {
    if (!aiResult?.markdown) return;
    if (saveNoteTarget === 'new') {
      const title = newNoteTitle.trim() || `AI Note: ${selectedDocData?.document?.title?.slice(0, 30)}...`;
      const res = await fetch(`${API}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title,
          content: aiResult.markdown,
          tags: ['ai_generated', selectedDocData?.document?.department?.toLowerCase() || 'research'],
          is_pinned: false
        })
      });
      const created = await res.json();
      await refreshAllData();
      setSelectedNoteId(created.id);
      setActiveView('note');
    } else {
      const existing = notes.find(n => n.id === saveNoteTarget);
      if (existing) {
        const appendedContent = `${existing.content}\n\n---\n\n${aiResult.markdown}`;
        await fetch(`${API}/notes/${saveNoteTarget}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: appendedContent })
        });
        await refreshAllData();
        setSelectedNoteId(saveNoteTarget);
        setActiveView('note');
      }
    }
    setShowSaveNoteModal(false);
  };

  const handleCreateNewNote = async () => {
    const res = await fetch(`${API}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Untitled Research Note',
        content: '# Research Thoughts\n\nConnect to [[MIMIC-IV]] or [[Federated Learning]]...',
        tags: ['notes'],
        is_pinned: false
      })
    });
    const created = await res.json();
    await refreshAllData();
    setSelectedNoteId(created.id);
    setActiveView('note');
  };

  const handleNoteChange = (field, value) => {
    if (!selectedNote) return;
    const noteId = selectedNote.id;
    const updated = { ...selectedNote, [field]: value };
    setSelectedNote(updated);
    setNotes(prev => prev.map(n => n.id === noteId ? { ...n, [field]: value } : n));
    setNoteSaveStatus('saving');
    clearTimeout(noteAutosaveTimer.current);
    noteAutosaveTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/notes/${noteId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [field]: value })
        });
        const saved = await res.json();
        if (!res.ok) throw new Error(saved.detail || 'Unable to save note');
        setNotes(prev => prev.map(n => n.id === noteId ? { ...n, ...saved } : n));
        setSelectedNote(current => current?.id === noteId ? { ...current, ...saved } : current);
        setNoteSaveStatus('saved');
      } catch (err) {
        console.error('Autosave failed:', err);
        setNoteSaveStatus('error');
      }
    }, 500);
  };

  const handleDeleteNote = async (noteId) => {
    setDeleteLoading(true);
    try {
      const res = await fetch(`${API}/notes/${noteId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to delete note');
      }
      await refreshAllData();
      if (selectedNoteId === noteId) {
        setSelectedNoteId(null);
        setSelectedNote(null);
        setActiveView('home');
      }
      setDeleteModal({ open: false, type: null, item: null });
    } catch (err) {
      throw err;
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDeleteDocument = async (docId) => {
    setDeleteLoading(true);
    try {
      const res = await fetch(`${API}/documents/${docId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to delete document');
      }
      await refreshAllData();
      if (selectedDocId === docId) {
        setSelectedDocId(null);
        setSelectedDocData(null);
        setActiveView('home');
      }
      setDeleteModal({ open: false, type: null, item: null });
    } catch (err) {
      throw err;
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleRenameDocument = async (docId) => {
    if (!renameValue.trim()) return;
    setRenameLoading(true);
    try {
      const res = await fetch(`${API}/documents/${docId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: renameValue.trim() })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to rename');
      }
      const data = await res.json();
      setDocuments(prev => prev.map(d => d.id === docId ? { ...d, title: data.title } : d));
      if (selectedDocId === docId && selectedDocData) {
        setSelectedDocData(prev => ({ ...prev, document: { ...prev.document, title: data.title } }));
      }
      setRenameModal({ open: false, type: null, item: null });
    } catch (err) {
      throw err;
    } finally {
      setRenameLoading(false);
    }
  };

  const handleRenameNote = async (noteId) => {
    if (!renameValue.trim()) return;
    setRenameLoading(true);
    try {
      const res = await fetch(`${API}/notes/${noteId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: renameValue.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to rename');
      setNotes(prev => prev.map(n => n.id === noteId ? { ...n, title: data.title } : n));
      if (selectedNoteId === noteId) {
        setSelectedNote(prev => prev ? { ...prev, title: data.title } : prev);
      }
      setRenameModal({ open: false, type: null, item: null });
    } catch (err) {
      throw err;
    } finally {
      setRenameLoading(false);
    }
  };

  const performSearch = useCallback(async (query) => {
    if (!query.trim()) {
      setSearchResults({ documents: [], notes: [], entities: [] });
      return;
    }
    setSearchLoading(true);
    try {
      const q = encodeURIComponent(query.trim());
      const [docRes, noteRes, entRes] = await Promise.allSettled([
        fetch(`${API}/search?q=${q}`).then(r => r.ok ? r.json() : []),
        fetch(`${API}/notes?q=${q}`).then(r => r.ok ? r.json() : []),
        fetch(`${API}/entities`).then(r => r.ok ? r.json() : [])
      ]);
      const docResults = docRes.status === 'fulfilled' ? (Array.isArray(docRes.value) ? docRes.value : []) : [];
      const noteResults = noteRes.status === 'fulfilled' ? (Array.isArray(noteRes.value) ? noteRes.value : []) : [];
      const allEntities = entRes.status === 'fulfilled' ? (Array.isArray(entRes.value) ? entRes.value : []) : [];
      const qLower = query.trim().toLowerCase();
      const entResults = allEntities.filter(e => e.name && e.name.toLowerCase().includes(qLower)).slice(0, 10);
      setSearchResults({ documents: docResults, notes: noteResults, entities: entResults });
    } catch {
      setSearchResults({ documents: [], notes: [], entities: [] });
    } finally {
      setSearchLoading(false);
    }
  }, []);

  const handleSearchChange = useCallback((q) => {
    setSearchQuery(q);
    clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => performSearch(q), 200);
  }, [performSearch]);

  const handleDuplicateNote = async (noteId) => {
    const res = await fetch(`${API}/notes/${noteId}/duplicate`, { method: 'POST' });
    const dup = await res.json();
    await refreshAllData();
    setSelectedNoteId(dup.id);
  };

  const handleRunCompare = async () => {
    if (!compareDocA || !compareDocB) return;
    setCompareLoading(true);
    try {
      const res = await fetch(`${API}/ai/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id_a: compareDocA, document_id_b: compareDocB })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Comparison failed');
      setCompareResult(data);
    } catch (err) {
      console.error('Compare failed:', err);
      setCompareResult({ markdown: `### Comparison unavailable\n\n${err.message}`, status: 'unavailable', error: err.message });
    } finally {
      setCompareLoading(false);
    }
  };

  const handlePerformUpload = async (retryDocId = null) => {
    console.log('[UPLOAD FLOW] handlePerformUpload called, retryDocId:', retryDocId, typeof retryDocId);

    if (!uploadFile && !retryDocId) {
      console.log('[UPLOAD FLOW] ABORTED: no file selected and no retryDocId');
      return;
    }

    setUploading(true);
    setUploadError('');

    let docId = retryDocId || null;

    try {
      if (!docId) {
        console.log('[UPLOAD FLOW] selected file:', {
          name: uploadFile?.name,
          type: uploadFile?.type,
          size: uploadFile?.size,
        });
        setUploadStep(1);
        console.log('[UPLOAD FLOW] sending upload request');

        const formData = new FormData();
        formData.append('file', uploadFile);
        const upRes = await fetch(`${API}/upload`, {
          method: 'POST',
          body: formData,
          signal: AbortSignal.timeout(120000),
        });
        const upData = await upRes.json();
        console.log('[UPLOAD RESPONSE]', upData);
        console.log('[UPLOAD RESPONSE JSON]', JSON.stringify(upData, null, 2));
        if (!upRes.ok) throw new Error(upData.detail || 'Unable to upload document');

        const rawId = upData?.id;
        console.log('[UPLOAD FLOW] raw upload ID:', rawId);
        console.log('[UPLOAD FLOW] raw upload ID type:', typeof rawId);

        if (!isValidDocumentId(rawId)) {
          throw new Error(
            `Upload succeeded, but the server did not return a valid document ID. Received: ${JSON.stringify(rawId)}`
          );
        }

        docId = rawId.trim();
        setUploadDocId(docId);
        console.log('[UPLOAD FLOW] validated document ID:', docId);
      }

      if (!isValidDocumentId(docId)) {
        throw new Error('Invalid document ID for analysis');
      }

      setUploadStep(2);
      console.log('[UPLOAD FLOW] starting analyze for docId:', docId);
      const analysis = await analyzeDocument(docId);
      console.log('[UPLOAD FLOW] analyze completed:', analysis);

      setUploadStep(3);
      console.log('[UPLOAD FLOW] workspace opening for doc:', docId);
      await refreshAllData();
      setSelectedDocId(docId);
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadStep(0);
      setUploadError('');
      setUploadDocId(null);
      setActiveView('document');
      setDocTab('overview');
      console.log('[UPLOAD FLOW] workspace opened successfully');
    } catch (err) {
      console.error('[UPLOAD FLOW] error:', err);
      setUploadError(err.message);
      setUploadStep(docId && isValidDocumentId(docId) ? 2 : 0);
    } finally {
      setUploading(false);
    }
  };

  const handleRetryAnalysis = async () => {
    const documentId =
      typeof uploadDocId === 'string'
        ? uploadDocId.trim()
        : '';

    console.log('[RETRY] uploadDocId:', uploadDocId);
    console.log('[RETRY] type:', typeof uploadDocId);

    if (!isValidDocumentId(documentId)) {
      setUploadError(
        'No valid document ID available for retry. Please upload the document again.'
      );
      return;
    }

    try {
      setUploading(true);
      setUploadError('');
      setUploadStep(2);

      await analyzeDocument(documentId);

      console.log('[RETRY] analysis successful:', documentId);

      await refreshAllData();

      setUploading(false);
      setUploadStep(3);

      setSelectedDocId(documentId);
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadStep(0);
      setUploadError('');
      setUploadDocId(null);
      setActiveView('document');
      setDocTab('overview');
      console.log('[RETRY] workspace opened for doc:', documentId);
    } catch (error) {
      console.error('[RETRY ERROR]', error);
      setUploading(false);
      setUploadError(
        error instanceof Error
          ? error.message
          : 'Analysis failed. Please try again.'
      );
    }
  };

  const handleResetDemoData = async () => {
    const res = await fetch(`${API}/reset/demo`, { method: 'POST' });
    if (!res.ok) throw new Error('Unable to reset demo data');
    await refreshAllData();
    setShowResetConfirm(false);
    setActiveView('home');
    setSelectedDocId(null);
    setSelectedDocData(null);
  };

  const handleResetWorkspace = async () => {
    const res = await fetch(`${API}/reset/workspace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: true })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Unable to reset workspace');
    setSelectedDocId(null);
    setSelectedDocData(null);
    setSelectedNoteId(null);
    setSelectedNote(null);
    setAiResult(null);
    await refreshAllData();
    setShowResetConfirm(false);
    setActiveView('home');
  };

  const handleWikilinkClick = (linkName) => {
    const matchedNote = notes.find(n => n.title.toLowerCase() === linkName.toLowerCase());
    if (matchedNote) { setSelectedNoteId(matchedNote.id); setActiveView('note'); return; }
    const matchedDoc = documents.find(d => d.title.toLowerCase().includes(linkName.toLowerCase()));
    if (matchedDoc) { setSelectedDocId(matchedDoc.id); setActiveView('document'); return; }
    setFocusGraphNodeId(linkName);
    setActiveView('graph');
  };

  useEffect(() => {
    const handler = (e) => {
      const isInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === 'k') {
        e.preventDefault();
        setSearchModal(prev => !prev);
      } else if (mod && e.key === 'u') {
        e.preventDefault();
        setShowUploadModal(true);
      } else if (mod && e.key === 'n' && !isInput) {
        e.preventDefault();
        handleCreateNewNote();
      } else if (e.key === 'Escape') {
        if (searchModal) setSearchModal(false);
        else if (showUploadModal) setShowUploadModal(false);
        else if (deleteModal.open) setDeleteModal({ open: false, type: null, item: null });
        else if (renameModal.open) setRenameModal({ open: false, type: null, item: null });
        else if (showSaveNoteModal) setShowSaveNoteModal(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [searchModal, showUploadModal, deleteModal.open, renameModal.open, showSaveNoteModal, handleCreateNewNote]);

  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const showLanding = activeView === 'home' || (activeView === 'document' && !selectedDocData);

  return (
    <div className="flex h-screen w-screen overflow-hidden theme-bg-app theme-text-primary text-[13px] antialiased">

      {mockAiEnabled && (
        <div className="absolute top-3 left-1/2 transform -translate-x-1/2 z-50 px-4 py-1.5 rounded-lg bg-yellow-50 border border-yellow-200 text-yellow-800 text-[11px] font-medium shadow-sm">
          Running in MOCK AI mode — AI outputs may be simulated.
        </div>
      )}

      {/* ================================================================ */}
      {/* SIDEBAR                                                          */}
      {/* ================================================================ */}
      <aside className={`${sidebarCollapsed ? 'w-[60px]' : 'w-[240px]'} flex flex-col shrink-0 border-r theme-border theme-bg-sidebar transition-all duration-200`}>

        {/* Header */}
        <div className={`${sidebarCollapsed ? 'px-2 justify-center' : 'px-3 justify-between'} py-3 flex items-center border-b theme-border`}>
          <div className="flex items-center gap-2 cursor-pointer min-w-0" onClick={() => { setActiveView('home'); setSelectedDocId(null); setSelectedDocData(null); }}>
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0 shadow-sm">RN</div>
            {!sidebarCollapsed && <span className="font-bold text-[13px] tracking-tight theme-text-primary truncate">Research Nexus</span>}
          </div>
          <div className="flex items-center gap-1">
            {!sidebarCollapsed && (
              <button onClick={() => setSearchModal(true)} className="p-1 rounded-md hover:theme-bg-elevated theme-text-muted transition-colors" title="Search (⌘K)">
                <Search size={14} />
              </button>
            )}
            <button onClick={() => setSidebarCollapsed(!sidebarCollapsed)} className={`${sidebarCollapsed ? 'hidden' : ''} p-1 rounded-md hover:theme-bg-elevated theme-text-muted transition-colors`}>
              <ChevronLeft size={14} />
            </button>
          </div>
        </div>

        {/* Collapsed toggle */}
        {sidebarCollapsed && (
          <div className="px-2 py-1.5 flex justify-center">
            <button onClick={() => setSidebarCollapsed(false)} className="p-1.5 rounded-md hover:theme-bg-elevated theme-text-muted transition-colors">
              <ChevronRight size={14} />
            </button>
          </div>
        )}

        {/* New Research */}
        <div className={`${sidebarCollapsed ? 'px-2' : 'px-3'} py-2`}>
          <button
            onClick={() => setShowUploadModal(true)}
            className={`w-full flex items-center ${sidebarCollapsed ? 'justify-center' : 'gap-2'} px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12px] font-semibold transition-colors shadow-sm`}
          >
            <Plus size={14} />
            {!sidebarCollapsed && <span>New Research</span>}
          </button>
        </div>

        {/* Navigation */}
        <nav className={`${sidebarCollapsed ? 'px-2' : 'px-2'} py-1 space-y-0.5`}>
          {[
            { key: 'home', icon: Home, label: 'Home', action: () => { setActiveView('home'); setSelectedDocId(null); setSelectedDocData(null); } },
            { key: 'document', icon: FileText, label: 'Documents', action: () => { setActiveView('home'); } },
            { key: 'note', icon: Edit3, label: 'Notes', action: () => setActiveView('note') },
            { key: 'graph', icon: Network, label: 'Knowledge Graph', action: () => setActiveView('graph') },
            { key: 'ai-assistant', icon: MessageSquare, label: 'AI Assistant', action: () => { if (selectedDocId) { setDocTab('ai'); setActiveView('document'); } else { setActiveView('home'); } } },
            { key: 'settings', icon: Sliders, label: 'Settings', action: () => setActiveView('settings') },
          ].map(item => {
            const isActive = (item.key === 'home' && (activeView === 'home' || showLanding))
              || (item.key === 'document' && activeView === 'document' && selectedDocData)
              || (item.key === item.key && activeView === item.key);
            return (
              <button
                key={item.key}
                onClick={item.action}
                className={`w-full flex items-center ${sidebarCollapsed ? 'justify-center' : ''} gap-2 px-2.5 py-1.5 rounded-lg text-[12px] font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300'
                    : 'theme-text-secondary hover:theme-bg-elevated hover:theme-text-primary'
                }`}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <item.icon size={15} className="shrink-0" />
                {!sidebarCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Scrollable Lists */}
        {!sidebarCollapsed && (
          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-3">

            {/* Documents */}
            <div>
              <div className="flex items-center justify-between px-1.5 py-1">
                <span className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Documents ({documents.length})</span>
              </div>
              <div className="space-y-0.5">
                {documents.map(doc => (
                  <div key={doc.id} className="group relative">
                    <button
                      onClick={() => { setSelectedDocId(doc.id); setActiveView('document'); setDocTab('overview'); }}
                      className={`w-full text-left px-2 py-1.5 rounded-lg transition-colors ${
                        selectedDocId === doc.id && activeView === 'document'
                          ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-medium'
                          : 'theme-text-secondary hover:theme-bg-elevated hover:theme-text-primary'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium line-clamp-1 text-[11px] flex-1">{doc.title}</span>
                        <span className="text-[8px] px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono shrink-0 theme-text-muted">
                          {doc.document_type || 'PDF'}
                        </span>
                      </div>
                      <div className="text-[10px] theme-text-muted mt-0.5 truncate">{doc.department}</div>
                    </button>
                    <details className="absolute right-1 top-1 z-20">
                      <summary className="list-none cursor-pointer p-0.5 rounded opacity-0 group-hover:opacity-100 hover:theme-bg-elevated transition-opacity">
                        <MoreVertical size={12} className="theme-text-muted" />
                      </summary>
                      <div className="absolute z-30 right-0 top-5 w-36 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                        <button onClick={() => { setSelectedDocId(doc.id); setActiveView('document'); setDocTab('overview'); }}
                          className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                          Open
                        </button>
                        <button onClick={() => { setRenameModal({ open: true, type: 'document', item: doc }); setRenameValue(doc.title); }}
                          className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                          Rename
                        </button>
                        <button onClick={() => setDeleteModal({ open: true, type: 'document', item: doc })}
                          className="block w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">
                          Delete
                        </button>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div>
              <div className="flex items-center justify-between px-1.5 py-1">
                <span className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Notes ({notes.length})</span>
                <button onClick={handleCreateNewNote} className="text-indigo-600 dark:text-indigo-400 hover:underline text-[10px] font-semibold flex items-center gap-0.5">
                  <Plus size={10} /> New
                </button>
              </div>
              <div className="space-y-0.5">
                {notes.map(note => (
                  <div key={note.id} className="group relative">
                    <button
                      onClick={() => { setSelectedNoteId(note.id); setActiveView('note'); }}
                      className={`w-full text-left px-2 py-1.5 rounded-lg transition-colors ${
                        selectedNoteId === note.id && activeView === 'note'
                          ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 font-medium'
                          : 'theme-text-secondary hover:theme-bg-elevated hover:theme-text-primary'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        {note.is_pinned === 1 && <Pin size={9} className="text-amber-500 fill-amber-500 shrink-0" />}
                        <span className="font-medium line-clamp-1 text-[11px]">{note.title}</span>
                      </div>
                    </button>
                    <details className="absolute right-1 top-1 z-20">
                      <summary className="list-none cursor-pointer p-0.5 rounded opacity-0 group-hover:opacity-100 hover:theme-bg-elevated transition-opacity">
                        <MoreVertical size={12} className="theme-text-muted" />
                      </summary>
                      <div className="absolute z-30 right-0 top-5 w-36 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                        <button onClick={() => { setSelectedNoteId(note.id); setActiveView('note'); }}
                          className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                          Open
                        </button>
                        <button onClick={() => { setRenameModal({ open: true, type: 'note', item: note }); setRenameValue(note.title); }}
                          className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                          Rename
                        </button>
                        <button onClick={() => setDeleteModal({ open: true, type: 'note', item: note })}
                          className="block w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">
                          Delete
                        </button>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className={`${sidebarCollapsed ? 'px-2' : 'px-3'} py-2.5 border-t theme-border flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'} text-[11px] theme-text-muted`}>
          <button
            onClick={() => setTheme(prev => prev === 'light' ? 'dark' : prev === 'dark' ? 'system' : 'light')}
            className="p-1.5 rounded-md hover:theme-bg-elevated transition-colors"
            title={`Theme: ${theme}`}
          >
            {theme === 'light' ? <Sun size={13} className="text-amber-500" /> : theme === 'dark' ? <Moon size={13} className="text-indigo-400" /> : <Monitor size={13} />}
          </button>
          {!sidebarCollapsed && (
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${health?.mock_ai_mode ? 'bg-amber-500' : 'bg-emerald-500'}`} />
              <span className="truncate">{health?.ai_engine?.mode || 'OpenRouter'}</span>
            </div>
          )}
        </div>
      </aside>

      {/* ================================================================ */}
      {/* MAIN CONTENT                                                     */}
      {/* ================================================================ */}
      <main className="flex-1 flex flex-col overflow-hidden theme-bg-app">

        {/* ============================================================ */}
        {/* LANDING PAGE                                                 */}
        {/* ============================================================ */}
        {showLanding && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-2xl w-full text-center space-y-8">
              <div className="space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold text-lg mx-auto shadow-lg">RN</div>
                <h1 className="text-2xl font-bold theme-text-primary">Research Nexus</h1>
                <p className="text-[13px] theme-text-muted max-w-md mx-auto leading-relaxed">
                  Turn your research into a connected knowledge workspace.
                  Upload documents and immediately understand them through AI analysis.
                </p>
              </div>

              <div>
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-[13px] shadow-lg transition-colors"
                >
                  Upload Research
                </button>
                <p className="text-[11px] theme-text-muted mt-3">
                  Drop PDF, Markdown, TXT or code files here
                </p>
              </div>

              {documents.length > 0 && (
                <div className="pt-6 border-t theme-border">
                  <h3 className="text-[11px] font-bold uppercase tracking-wider theme-text-muted mb-3">Recent Research</h3>
                  <div className="grid grid-cols-2 gap-2 max-w-lg mx-auto">
                    {documents.slice(0, 4).map(doc => (
                      <div key={doc.id} className="relative group">
                        <button
                          onClick={() => { setSelectedDocId(doc.id); setActiveView('document'); setDocTab('overview'); }}
                          className="p-3 rounded-xl theme-bg-surface border theme-border text-left hover:theme-bg-elevated transition-colors w-full"
                        >
                          <div className="flex items-center gap-1.5 mb-1.5">
                            <span className="text-[8px] px-1 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-mono uppercase">
                              {doc.document_type || 'PDF'}
                            </span>
                          </div>
                          <span className="text-[11px] font-semibold line-clamp-2 theme-text-primary group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                            {doc.title}
                          </span>
                          <span className="text-[10px] theme-text-muted block mt-1">{doc.department}</span>
                        </button>
                        <details className="absolute top-2 right-2 z-20">
                          <summary className="list-none cursor-pointer p-0.5 rounded opacity-0 group-hover:opacity-100 hover:theme-bg-elevated transition-opacity">
                            <MoreVertical size={12} className="theme-text-muted" />
                          </summary>
                          <div className="absolute z-30 right-0 top-5 w-36 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                            <button onClick={() => { setSelectedDocId(doc.id); setActiveView('document'); setDocTab('overview'); }}
                              className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                              Open
                            </button>
                            <button onClick={() => { setRenameModal({ open: true, type: 'document', item: doc }); setRenameValue(doc.title); }}
                              className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                              Rename
                            </button>
                            <button onClick={() => setDeleteModal({ open: true, type: 'document', item: doc })}
                              className="block w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">
                              Delete
                            </button>
                          </div>
                        </details>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* DOCUMENT WORKSPACE                                           */}
        {/* ============================================================ */}
        {activeView === 'document' && selectedDocData && (
          <div className="flex-1 flex flex-col h-full overflow-hidden">

            {/* Header */}
            <div className="px-5 py-3 border-b theme-border theme-bg-surface shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded-md bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-mono uppercase shrink-0">
                    {selectedDocData.document.document_type}
                  </span>
                  <div className="min-w-0">
                    <h2 className="text-[14px] font-bold theme-text-primary leading-tight truncate">{selectedDocData.document.title}</h2>
                    <div className="flex items-center gap-1.5 text-[10px] theme-text-muted mt-0.5">
                      <span>{selectedDocData.document.department}</span>
                      {selectedDocData.entities?.find(e => e.entity_type === 'RESEARCHER') && (
                        <>
                          <span className="theme-text-muted">·</span>
                          <span>{selectedDocData.entities.find(e => e.entity_type === 'RESEARCHER').name}</span>
                        </>
                      )}
                      <span className="theme-text-muted">·</span>
                      <span>{selectedDocData.entities?.length || 0} entities</span>
                    </div>
                  </div>
                </div>
                <div className="relative">
                  <details>
                    <summary className="list-none cursor-pointer p-1.5 rounded-lg border theme-border hover:theme-bg-elevated theme-text-muted transition-colors">
                      <MoreVertical size={14} />
                    </summary>
                    <div className="absolute z-30 right-0 top-7 w-36 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                      <button onClick={() => { setDocTab('overview'); }}
                        className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                        Open
                      </button>
                      <button onClick={() => { setRenameModal({ open: true, type: 'document', item: selectedDocData.document }); setRenameValue(selectedDocData.document.title); }}
                        className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                        Rename
                      </button>
                      <button onClick={() => setDeleteModal({ open: true, type: 'document', item: selectedDocData.document })}
                        className="block w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">
                        Delete
                      </button>
                    </div>
                  </details>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex items-center gap-0.5 mt-3">
                {[
                  ['overview', 'Overview'],
                  ['ai', 'AI Assistant'],
                  ['text', 'Document'],
                  ['entities', 'Entities'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setDocTab(key)}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors ${
                      docTab === key
                        ? 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-semibold'
                        : 'theme-text-muted hover:theme-text-secondary hover:theme-bg-elevated'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* AI Action Toolbar */}
            <div className="px-5 py-1.5 border-b theme-border theme-bg-surface flex items-center gap-1 overflow-x-auto shrink-0">
              {[
                ['summarize', 'Summarize'],
                ['analyze', 'Deep Analysis'],
                ['explain', 'Explain'],
                ['methodology', 'Methodology'],
                ['questions', 'Questions'],
                ['ideas', 'Ideas'],
              ].map(([actionKey, actionLabel]) => (
                <button
                  key={actionKey}
                  onClick={() => triggerAiAction(actionKey)}
                  disabled={aiLoading}
                  className={`px-2 py-1 rounded-md text-[11px] font-medium border theme-border transition-all flex items-center gap-1 whitespace-nowrap ${
                    aiLoadingAction === actionKey && aiLoading
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'theme-text-secondary hover:theme-bg-elevated hover:theme-text-primary'
                  }`}
                >
                  {aiLoadingAction === actionKey && aiLoading && (
                    <span className="w-1.5 h-1.5 border-[1.5px] border-current border-t-transparent rounded-full animate-spin" />
                  )}
                  {actionLabel}
                </button>
              ))}
              <details className="relative ml-0.5">
                <summary className="list-none cursor-pointer px-2 py-1 rounded-md text-[11px] font-medium border theme-border theme-text-secondary hover:theme-bg-elevated">
                  More...
                </summary>
                <div className="absolute z-30 top-7 left-0 w-44 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                  {[
                    ['findings', 'Key Findings'],
                    ['contributions', 'Key Contributions'],
                    ['research-questions', 'Research Questions'],
                    ['datasets', 'Datasets'],
                    ['technologies', 'Technologies'],
                    ['results', 'Important Results'],
                    ['limitations', 'Limitations'],
                    ['future-work', 'Future Work'],
                    ['concepts', 'Extract Concepts'],
                    ['generate_note', 'Generate Note'],
                  ].map(([key, label]) => (
                    <button key={key} onClick={() => triggerAiAction(key)} disabled={aiLoading}
                      className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated disabled:opacity-50 transition-colors">
                      {label}
                    </button>
                  ))}
                </div>
              </details>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto">

              {/* OVERVIEW TAB */}
              {docTab === 'overview' && (
                <div className="max-w-3xl mx-auto p-6 space-y-6">
                  {/* Document Info */}
                  <div className="p-4 rounded-xl theme-bg-surface border theme-border space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-indigo-100 dark:bg-indigo-950/60 flex items-center justify-center shrink-0">
                        <FileText size={16} className="text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-[13px] font-bold theme-text-primary truncate">{selectedDocData.document.title}</h3>
                        <div className="flex items-center gap-2 text-[10px] theme-text-muted mt-0.5">
                          <span>{selectedDocData.document.document_type}</span>
                          <span>·</span>
                          <span>{selectedDocData.document.department}</span>
                          <span>·</span>
                          <span>{selectedDocData.document.created_at ? new Date(selectedDocData.document.created_at).toLocaleDateString() : 'Recently uploaded'}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {aiLoading ? (
                    <div className="py-16 text-center space-y-3">
                      <Sparkles size={22} className="text-indigo-600 dark:text-indigo-400 animate-spin mx-auto" />
                      <p className="text-[13px] font-semibold theme-text-primary">Analyzing research...</p>
                      <p className="text-[11px] theme-text-muted">Extracting insights, key findings, and connections.</p>
                    </div>
                  ) : aiResult ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-[10px] theme-text-muted">
                          <span className={`w-1.5 h-1.5 rounded-full ${aiResult.status === 'success' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                          <span>{aiResult.provider || 'AI Analysis'}</span>
                          {aiResult.status === 'success' && primaryModel && aiResult.provider && !aiResult.provider.includes(primaryModel) && (
                            <span className="px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 text-[9px] font-medium">
                              Served via fallback
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => navigator.clipboard.writeText(aiResult.markdown)}
                            className="px-2 py-1 rounded-md border theme-border hover:theme-bg-elevated flex items-center gap-1 text-[10px] font-medium theme-text-secondary transition-colors"
                          >
                            <Copy size={11} /> Copy
                          </button>
                          <button
                            onClick={() => setShowSaveNoteModal(true)}
                            disabled={aiResult.status !== 'success'}
                            className="px-2 py-1 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1 text-[10px] font-semibold disabled:opacity-50 transition-colors"
                          >
                            <Save size={11} /> Save to Note
                          </button>
                        </div>
                      </div>
                      <div className="p-5 rounded-xl theme-bg-surface border theme-border">
                        <MarkdownViewer content={aiResult.markdown} onWikilinkClick={handleWikilinkClick} />
                      </div>
                    </div>
                  ) : (
                    <div className="py-16 text-center space-y-3">
                      <Sparkles size={22} className="text-indigo-400 mx-auto" />
                      <p className="text-[12px] theme-text-muted">Click an AI action above to analyze this research document.</p>
                    </div>
                  )}

                  {/* Key Concepts */}
                  {selectedDocData.entities?.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Key Concepts</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedDocData.entities.slice(0, 15).map(ent => (
                          <button
                            key={ent.id}
                            onClick={() => { setFocusGraphNodeId(ent.id); setActiveView('graph'); }}
                            className="px-2 py-0.5 rounded-md border theme-border hover:theme-bg-elevated text-[10px] font-medium flex items-center gap-1 transition-colors"
                          >
                            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_COLORS[ent.entity_type] || '#64748b' }} />
                            <span>{ent.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Suggested Actions */}
                  <div className="space-y-2">
                    <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Suggested Actions</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        ['explain', 'Explain Simply'],
                        ['methodology', 'Methodology'],
                        ['research-questions', 'Research Questions'],
                        ['ideas', 'Research Ideas'],
                        ['generate_note', 'Generate Note'],
                        ['findings', 'Key Findings'],
                      ].map(([key, label]) => (
                        <button
                          key={key}
                          onClick={() => triggerAiAction(key)}
                          disabled={aiLoading}
                          className="px-2.5 py-1 rounded-md border theme-border text-[11px] font-medium theme-text-secondary hover:theme-bg-elevated hover:theme-text-primary transition-colors disabled:opacity-50"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* AI TAB (Chat with Sources) */}
              {docTab === 'ai' && (
                <div className="max-w-2xl mx-auto flex flex-col h-full p-4">
                  <div className="flex-1 space-y-2 overflow-y-auto pb-4">
                    {chatMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] p-3 rounded-xl text-[12px] space-y-1 ${
                          msg.role === 'user'
                            ? 'bg-indigo-600 text-white rounded-br-sm'
                            : 'theme-bg-surface border theme-border rounded-bl-sm'
                        }`}>
                          <MarkdownViewer content={msg.text} onWikilinkClick={handleWikilinkClick} />
                          {msg.sources?.length > 0 && (
                            <div className="pt-1.5 mt-1.5 border-t theme-border text-[10px] theme-text-muted">
                              <span className="font-semibold">Source:</span> {msg.sources.join(', ')}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="flex items-center gap-1.5 text-[11px] theme-text-muted py-1">
                        <Sparkles size={11} className="animate-spin text-indigo-600" />
                        <span>Thinking...</span>
                      </div>
                    )}
                  </div>
                  <div className="sticky bottom-0 pt-2">
                    <div className="flex items-center gap-2 p-2 rounded-xl theme-bg-surface border theme-border">
                      <input
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                        placeholder="Ask about this research..."
                        className="flex-1 px-2 py-1 text-[12px] bg-transparent outline-none theme-text-primary"
                      />
                      <button
                        onClick={handleSendChat}
                        disabled={chatLoading || !chatInput.trim()}
                        className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 transition-colors"
                      >
                        <Send size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* DOCUMENT TEXT TAB */}
              {docTab === 'text' && (
                <div className="max-w-3xl mx-auto p-6">
                  <div className="p-5 rounded-xl theme-bg-surface border theme-border">
                    <MarkdownViewer content={selectedDocData.document.content} onWikilinkClick={handleWikilinkClick} />
                  </div>
                </div>
              )}

              {/* ENTITIES TAB */}
              {docTab === 'entities' && (
                <div className="max-w-3xl mx-auto p-6 space-y-4">
                  <div className="flex flex-wrap gap-1.5">
                    {selectedDocData.entities?.map(ent => (
                      <button
                        key={ent.id}
                        onClick={() => { setFocusGraphNodeId(ent.id); setActiveView('graph'); }}
                        className="px-2.5 py-1 rounded-lg border theme-border hover:theme-bg-elevated text-[11px] font-medium flex items-center gap-1.5 transition-colors"
                      >
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: NODE_COLORS[ent.entity_type] || '#64748b' }} />
                        <span>{ent.name}</span>
                        <span className="text-[9px] theme-text-muted uppercase">({ent.entity_type})</span>
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => { setFocusGraphNodeId(selectedDocData.document.id); setActiveView('graph'); }}
                    className="w-full py-3 rounded-xl border theme-border hover:theme-bg-elevated text-[12px] font-medium flex items-center justify-center gap-2 transition-colors"
                  >
                    <Network size={14} />
                    Open Knowledge Graph
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* NOTES WORKSPACE                                              */}
        {/* ============================================================ */}
        {activeView === 'note' && (
          selectedNote ? (
            <div className="flex-1 flex h-full overflow-hidden">
              <div className="flex-1 flex flex-col h-full border-r theme-border overflow-hidden">
                <div className="px-5 py-3 border-b theme-border theme-bg-surface flex items-center justify-between shrink-0">
                  <div className="flex-1 mr-4 min-w-0">
                    <input
                      value={selectedNote.title}
                      onChange={(e) => handleNoteChange('title', e.target.value)}
                      className="w-full text-[14px] font-bold bg-transparent outline-none theme-text-primary"
                      placeholder="Note title..."
                    />
                    <div className="flex items-center gap-1.5 text-[10px] theme-text-muted mt-0.5">
                      <span>{selectedNote.wikilinks?.length || 0} wikilinks</span>
                      <span>·</span>
                      <span>{noteSaveStatus === 'saving' ? 'Saving...' : noteSaveStatus === 'error' ? 'Error' : 'Saved'}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-[10px] mr-2">
                      {['edit', 'split', 'preview'].map(mode => (
                        <button
                          key={mode}
                          onClick={() => setNoteEditMode(mode)}
                          className={`px-2 py-0.5 rounded-md font-medium capitalize transition-colors ${
                            noteEditMode === mode ? 'bg-white dark:bg-slate-900 shadow-sm font-semibold' : 'theme-text-muted hover:theme-text-secondary'
                          }`}
                        >
                          {mode}
                        </button>
                      ))}
                    </div>
                    <button onClick={() => handleNoteChange('is_pinned', selectedNote.is_pinned === 1 ? 0 : 1)}
                      className={`p-1.5 rounded-lg border theme-border hover:theme-bg-elevated transition-colors ${selectedNote.is_pinned === 1 ? 'text-amber-500 fill-amber-500' : 'theme-text-muted'}`}>
                      <Pin size={13} />
                    </button>
                    <button onClick={() => handleDuplicateNote(selectedNote.id)}
                      className="p-1.5 rounded-lg border theme-border hover:theme-bg-elevated theme-text-muted transition-colors">
                      <Copy size={13} />
                    </button>
                    <div className="relative">
                      <details>
                        <summary className="list-none cursor-pointer p-1.5 rounded-lg border theme-border hover:theme-bg-elevated theme-text-muted transition-colors">
                          <MoreVertical size={13} />
                        </summary>
                        <div className="absolute z-30 right-0 top-7 w-36 py-1 rounded-xl theme-bg-surface border theme-border shadow-lg">
                          <button onClick={() => { setRenameModal({ open: true, type: 'note', item: selectedNote }); setRenameValue(selectedNote.title); }}
                            className="block w-full text-left px-3 py-1.5 text-[11px] theme-text-secondary hover:theme-bg-elevated">
                            Rename
                          </button>
                          <button onClick={() => setDeleteModal({ open: true, type: 'note', item: selectedNote })}
                            className="block w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40">
                            Delete
                          </button>
                        </div>
                      </details>
                    </div>
                  </div>
                </div>
                <div className="flex-1 flex overflow-hidden">
                  {(noteEditMode === 'edit' || noteEditMode === 'split') && (
                    <div className={`p-5 overflow-y-auto ${noteEditMode === 'split' ? 'w-1/2 border-r theme-border' : 'w-full'}`}>
                      <textarea
                        value={selectedNote.content}
                        onChange={(e) => handleNoteChange('content', e.target.value)}
                        placeholder="Write notes with [[Wikilinks]] (e.g. [[MIMIC-IV]], [[Federated Learning]])..."
                        className="w-full h-full bg-transparent outline-none resize-none text-[12px] leading-relaxed theme-text-primary"
                        style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
                      />
                    </div>
                  )}
                  {(noteEditMode === 'preview' || noteEditMode === 'split') && (
                    <div className={`p-5 overflow-y-auto ${noteEditMode === 'split' ? 'w-1/2' : 'w-full'}`}>
                      <MarkdownViewer content={selectedNote.content} onWikilinkClick={handleWikilinkClick} />
                    </div>
                  )}
                </div>
              </div>

              {/* Backlinks Sidebar */}
              <div className="w-60 p-4 theme-bg-surface overflow-y-auto space-y-4 shrink-0">
                <div className="space-y-1.5">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Wikilinks</h4>
                  {selectedNote.wikilinks?.length > 0 ? (
                    selectedNote.wikilinks.map((link, i) => (
                      <button key={i} onClick={() => handleWikilinkClick(link)}
                        className="w-full text-left p-2 rounded-lg border theme-border hover:theme-bg-elevated flex items-center justify-between text-[11px] transition-colors">
                        <span className="font-semibold text-indigo-600 dark:text-indigo-400">[[{link}]]</span>
                        <CornerDownRight size={11} className="theme-text-muted" />
                      </button>
                    ))
                  ) : (
                    <p className="text-[10px] theme-text-muted leading-relaxed">
                      Type <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded text-[9px]">[[Concept]]</code> to create live links to papers, datasets, or notes.
                    </p>
                  )}
                </div>
                <div className="pt-3 border-t theme-border">
                  <button
                    onClick={() => { setFocusGraphNodeId(selectedNote.id); setGraphMode('note'); setActiveView('graph'); }}
                    className="w-full py-2 rounded-lg border theme-border hover:theme-bg-elevated text-[11px] font-medium flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Network size={13} /> View Graph
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-3">
                <Edit3 size={24} className="text-indigo-400 mx-auto" />
                <p className="text-[13px] theme-text-muted">Select a note from the sidebar or create a new one.</p>
                <button onClick={handleCreateNewNote} className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12px] font-semibold transition-colors">
                  Create Note
                </button>
              </div>
            </div>
          )
        )}

        {/* ============================================================ */}
        {/* KNOWLEDGE GRAPH VIEW                                         */}
        {/* ============================================================ */}
        {activeView === 'graph' && (
          <div className="flex-1 flex flex-col h-full p-4 space-y-3 overflow-hidden">
            <div className="flex items-center justify-between shrink-0 flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <h2 className="text-[14px] font-bold theme-text-primary">Knowledge Graph</h2>
                <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-[10px]">
                  {['global', 'note', 'document'].map(mode => (
                    <button key={mode} onClick={() => setGraphMode(mode)}
                      className={`px-2 py-0.5 rounded-md font-medium capitalize transition-colors ${graphMode === mode ? 'bg-white dark:bg-slate-900 shadow-sm font-semibold' : 'theme-text-muted'}`}>
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-0.5 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-[10px]">
                {['ALL', 'DATASET', 'PAPER', 'NOTE', 'RESEARCHER', 'METHOD'].map(t => (
                  <button key={t} onClick={() => setGraphFilter(t)}
                    className={`px-2 py-0.5 rounded-md font-medium transition-colors ${graphFilter === t ? 'bg-white dark:bg-slate-900 shadow-sm font-semibold' : 'theme-text-muted'}`}>
                    {t === 'ALL' ? 'All' : t.charAt(0) + t.slice(1).toLowerCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1 flex gap-3 overflow-hidden">
              <div className="flex-1">
                <KnowledgeGraphView data={graphData} selectedType={graphFilter} onSelectNode={setSelectedGraphNode} focusNodeId={focusGraphNodeId} isDark={isDark} />
              </div>
              {selectedGraphNode && (
                <div className="w-72 p-4 rounded-xl theme-bg-surface border theme-border overflow-y-auto space-y-3 shrink-0">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase"
                        style={{ backgroundColor: `${NODE_COLORS[selectedGraphNode.type] || '#64748b'}20`, color: NODE_COLORS[selectedGraphNode.type] || '#64748b' }}>
                        {selectedGraphNode.type}
                      </span>
                      <h3 className="text-[13px] font-bold mt-1 theme-text-primary">{selectedGraphNode.label}</h3>
                    </div>
                    <button onClick={() => setSelectedGraphNode(null)} className="theme-text-muted p-0.5 hover:theme-text-primary transition-colors"><X size={14} /></button>
                  </div>
                  {selectedGraphNode.description && (
                    <p className="text-[11px] theme-text-secondary leading-relaxed">{selectedGraphNode.description}</p>
                  )}
                  <button
                    onClick={async () => {
                      const res = await fetch(`${API}/notes`, {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          title: `Note: ${selectedGraphNode.label}`,
                          content: `# Research on [[${selectedGraphNode.label}]]\n\n- Type: ${selectedGraphNode.type}\n- Notes and hypotheses:`,
                          tags: ['graph_node']
                        })
                      });
                      const note = await res.json();
                      await refreshAllData();
                      setSelectedNoteId(note.id);
                      setActiveView('note');
                    }}
                    className="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Plus size={12} /> Create Note
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* COMPARE VIEW                                                 */}
        {/* ============================================================ */}
        {activeView === 'compare' && (
          <div className="flex-1 p-6 max-w-4xl mx-auto w-full overflow-y-auto space-y-5">
            <div className="space-y-1">
              <h2 className="text-[16px] font-bold theme-text-primary">Compare Documents</h2>
              <p className="text-[12px] theme-text-muted">Discover overlapping methodologies, shared datasets, and cross-department opportunities.</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-3 p-4 rounded-xl theme-bg-surface border theme-border">
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold theme-text-primary">Document A</label>
                <select value={compareDocA} onChange={(e) => setCompareDocA(e.target.value)}
                  className="w-full p-2.5 rounded-lg border theme-border theme-bg-app text-[12px] outline-none">
                  <option value="">Select document...</option>
                  {documents.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold theme-text-primary">Document B</label>
                <select value={compareDocB} onChange={(e) => setCompareDocB(e.target.value)}
                  className="w-full p-2.5 rounded-lg border theme-border theme-bg-app text-[12px] outline-none">
                  <option value="">Select document...</option>
                  {documents.map(d => <option key={d.id} value={d.id}>{d.title}</option>)}
                </select>
              </div>
            </div>
            <button onClick={handleRunCompare} disabled={compareLoading || !compareDocA || !compareDocB}
              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-[12px] disabled:opacity-50 flex items-center justify-center gap-2 transition-colors">
              {compareLoading && <Sparkles size={14} className="animate-spin" />}
              Compare with AI
            </button>
            {compareResult && (
              <div className="p-5 rounded-xl theme-bg-surface border theme-border space-y-3">
                <div className="flex items-center justify-between border-b theme-border pb-2">
                  <span className="text-[12px] font-bold theme-text-primary">Comparative Analysis</span>
                  <button onClick={async () => {
                    const res = await fetch(`${API}/notes`, {
                      method: 'POST', headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ title: 'Comparison: Document A vs B', content: compareResult.markdown, tags: ['comparison'] })
                    });
                    const note = await res.json();
                    await refreshAllData();
                    setSelectedNoteId(note.id);
                    setActiveView('note');
                  }} className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold transition-colors">
                    Save to Note
                  </button>
                </div>
                <MarkdownViewer content={compareResult.markdown} onWikilinkClick={handleWikilinkClick} />
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* INSIGHTS VIEW                                                */}
        {/* ============================================================ */}
        {activeView === 'insights' && (
          <div className="flex-1 p-6 max-w-4xl mx-auto w-full overflow-y-auto space-y-5">
            <div className="space-y-1">
              <h2 className="text-[16px] font-bold theme-text-primary">Research Insights</h2>
              <p className="text-[12px] theme-text-muted">Cross-department collaborations, dataset matches, and research overlap detection.</p>
            </div>
            <div className="space-y-2.5">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Cross-Department Collaborations</h3>
              {collaborations.length === 0 && <p className="text-[11px] theme-text-muted">No collaborations detected yet.</p>}
              {collaborations.map((c, i) => (
                <div key={i} className="p-4 rounded-xl theme-bg-surface border theme-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded-full">
                      {Math.round((c.score || 0.9) * 100)}% Synergy
                    </span>
                    <button onClick={() => { setFocusGraphNodeId(c.paper_a_id || c.department_a); setActiveView('graph'); }}
                      className="text-[10px] font-bold text-indigo-600 hover:underline transition-colors">Graph →</button>
                  </div>
                  <div className="text-[12px] font-bold theme-text-primary">{c.department_a} ↔ {c.department_b}</div>
                  <p className="text-[11px] theme-text-secondary">{c.explanation}</p>
                </div>
              ))}
            </div>
            <div className="space-y-2.5 pt-3 border-t theme-border">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Dataset Matches</h3>
              {(!datasetMatching.datasets || datasetMatching.datasets.length === 0) && <p className="text-[11px] theme-text-muted">No dataset matches found yet.</p>}
              {datasetMatching.datasets?.map((d, i) => (
                <div key={i} className="p-4 rounded-xl theme-bg-surface border theme-border space-y-1.5">
                  <span className="text-[10px] font-bold text-orange-600 bg-orange-50 dark:bg-orange-950/60 px-2 py-0.5 rounded-full">
                    Used across {d.total_departments} departments
                  </span>
                  <h4 className="text-[12px] font-bold theme-text-primary">{d.name}</h4>
                  <p className="text-[11px] theme-text-secondary">{d.highlight}</p>
                </div>
              ))}
            </div>
            <div className="space-y-2.5 pt-3 border-t theme-border">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Research Overlap</h3>
              {redundancies.length === 0 && <p className="text-[11px] theme-text-muted">No research overlap detected yet.</p>}
              {redundancies.map((r, i) => (
                <div key={i} className="p-4 rounded-xl theme-bg-surface border theme-border space-y-1.5">
                  <span className="text-[10px] font-bold text-amber-600 bg-amber-50 dark:bg-amber-950/60 px-2 py-0.5 rounded-full">
                    {Math.round((r.similarity || 0.85) * 100)}% Overlap
                  </span>
                  <div className="text-[11px] font-semibold theme-text-primary">"{r.paper_a}" ↔ "{r.paper_b}"</div>
                  <p className="text-[11px] theme-text-secondary">{r.recommendation}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* SETTINGS VIEW                                                */}
        {/* ============================================================ */}
        {activeView === 'settings' && (
          <div className="flex-1 p-6 max-w-xl mx-auto w-full overflow-y-auto space-y-5">
            <div className="space-y-1">
              <h2 className="text-[16px] font-bold theme-text-primary">Settings</h2>
              <p className="text-[12px] theme-text-muted">Configure appearance and workspace.</p>
            </div>
            <div className="p-4 rounded-xl theme-bg-surface border theme-border space-y-3">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Appearance</h3>
              <div className="grid grid-cols-3 gap-2">
                {['light', 'dark', 'system'].map(t => (
                  <button key={t} onClick={() => setTheme(t)}
                    className={`py-2 rounded-lg border text-[12px] font-semibold capitalize transition-all ${
                      theme === t ? 'bg-indigo-600 text-white border-indigo-600' : 'theme-border hover:theme-bg-elevated theme-text-secondary'
                    }`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-4 rounded-xl theme-bg-surface border theme-border space-y-2 text-[12px]">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">AI Engine</h3>
              <div className="flex justify-between py-1.5 border-b theme-border">
                <span className="theme-text-muted">Provider</span>
                <span className="font-semibold">OpenRouter</span>
              </div>
              <div className="flex justify-between py-1.5 border-b theme-border">
                <span className="theme-text-muted">Model</span>
                <span className="font-mono text-[11px]">{health?.ai_engine?.model || 'minimax/minimax-m3:free'}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="theme-text-muted">Status</span>
                <span className={health?.mock_ai_mode ? 'text-amber-600' : 'text-emerald-600'}>
                  {health?.mock_ai_mode ? 'Mock Mode' : 'Connected'}
                </span>
              </div>
            </div>
            <div className="p-4 rounded-xl theme-bg-surface border theme-border space-y-3">
              <h3 className="text-[10px] font-bold uppercase tracking-wider theme-text-muted">Data Management</h3>
              <button onClick={() => { setResetMode('demo'); setShowResetConfirm(true); }}
                className="w-full py-2 rounded-lg border border-red-200 dark:border-red-900 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 text-[12px] font-semibold transition-colors">
                Reset & Reseed Demo Data
              </button>
              <button onClick={() => { setResetMode('clear'); setShowResetConfirm(true); }}
                className="w-full py-2 rounded-lg border border-red-200 dark:border-red-900 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 text-[12px] font-semibold transition-colors">
                Clear Workspace
              </button>
            </div>
          </div>
        )}

        {/* Floating Upload Button */}
        {(activeView !== 'home' && activeView !== 'settings' && !showLanding) && (
          <div className="fixed right-5 bottom-5 z-40">
            <button onClick={() => setShowUploadModal(true)} title="Upload research"
              className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg text-[12px] font-semibold transition-colors">
              <Upload size={14} /> Upload
            </button>
          </div>
        )}
      </main>

      {/* ================================================================ */}
      {/* MODALS                                                           */}
      {/* ================================================================ */}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="theme-bg-surface w-full max-w-lg rounded-2xl border theme-border shadow-xl overflow-hidden">
            <div className="p-5 border-b theme-border flex items-center justify-between">
              <h3 className="text-[14px] font-bold theme-text-primary">Upload Research Document</h3>
              <button onClick={() => { setShowUploadModal(false); setUploadFile(null); setUploadStep(0); setUploadError(''); setUploading(false); }}
                className="theme-text-muted hover:theme-text-primary p-1 transition-colors"><X size={16} /></button>
            </div>
            <div className="p-5">
              {uploadStep === 0 && !uploading ? (
                <div className="space-y-4">
                  <div className="relative">
                    <label className="block">
                      <div className="relative border-2 border-dashed theme-border rounded-xl p-8 text-center space-y-2 cursor-pointer hover:border-indigo-500 transition-colors">
                        <input type="file" accept=".pdf,.txt,.md,.markdown,.zip,.py"
                          onChange={(e) => { e.target.files?.[0] && setUploadFile(e.target.files[0]); setUploadError(''); }}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" />
                        <Upload size={28} className="text-indigo-500 mx-auto pointer-events-none" />
                        <div className="text-[13px] font-semibold theme-text-primary pointer-events-none">
                          {uploadFile ? uploadFile.name : 'Choose a file or drag it here'}
                        </div>
                        <p className="text-[11px] theme-text-muted pointer-events-none">PDF, Markdown, TXT, or ZIP</p>
                      </div>
                    </label>
                  </div>
                  {uploadError && (
                    <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-[11px] text-red-700 dark:text-red-300">
                      {uploadError}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button onClick={() => handlePerformUpload()} disabled={!uploadFile}
                      className="flex-1 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12px] font-semibold disabled:opacity-50 transition-colors">
                      Upload & Analyze
                    </button>
                    <button onClick={() => { setUploadFile(null); setShowUploadModal(false); setUploadStep(0); setUploadError(''); }}
                      className="px-4 py-2.5 rounded-lg border theme-border text-[12px] theme-text-muted hover:theme-bg-elevated transition-colors">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Sparkles size={20} className="text-indigo-600 animate-spin" />
                    <div>
                      <div className="text-[13px] font-semibold theme-text-primary">
                        {uploadStep === 1 && 'Uploading file...'}
                        {uploadStep === 2 && 'Analyzing document...'}
                        {uploadStep === 3 && 'Opening workspace...'}
                      </div>
                      <div className="text-[11px] theme-text-muted mt-0.5">
                        {uploadStep === 1 && 'Sending file to server.'}
                        {uploadStep === 2 && 'Extracting text, entities, and relationships.'}
                        {uploadStep === 3 && 'Loading document data.'}
                      </div>
                    </div>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div className="h-full bg-indigo-600 transition-all duration-300 rounded-full"
                      style={{ width: `${uploadStep === 1 ? 33 : uploadStep === 2 ? 66 : 100}%` }} />
                  </div>
                  {uploadError && (
                    <div className="space-y-2">
                      <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-[11px] text-red-700 dark:text-red-300">
                        {uploadError}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setUploadError('')}
                          className="flex-1 py-2 rounded-lg border border-red-200 dark:border-red-800 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 text-[11px] font-semibold transition-colors">
                          Dismiss
                        </button>
                        <button
                          onClick={() => handleRetryAnalysis()}
                          className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold transition-colors">
                          Retry
                        </button>
                      </div>
                    </div>
                  )}
                  <button
                    onClick={() => { setUploading(false); setUploadStep(0); setUploadFile(null); setUploadError(''); setUploadDocId(null); }}
                    className="w-full py-2 rounded-lg border theme-border text-[11px] theme-text-muted hover:theme-bg-elevated transition-colors">
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Save to Note Modal */}
      {showSaveNoteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="theme-bg-surface w-full max-w-sm rounded-2xl border theme-border shadow-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-[14px] font-bold theme-text-primary">Save to Note</h3>
              <button onClick={() => setShowSaveNoteModal(false)} className="theme-text-muted hover:theme-text-primary p-1 transition-colors"><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <button onClick={() => setSaveNoteTarget('new')}
                  className={`py-2 rounded-lg border text-[12px] font-semibold transition-colors ${saveNoteTarget === 'new' ? 'bg-indigo-600 text-white border-indigo-600' : 'theme-border hover:theme-bg-elevated theme-text-secondary'}`}>
                  New Note
                </button>
                <button onClick={() => setSaveNoteTarget(notes[0]?.id || 'new')}
                  className={`py-2 rounded-lg border text-[12px] font-semibold transition-colors ${saveNoteTarget !== 'new' ? 'bg-indigo-600 text-white border-indigo-600' : 'theme-border hover:theme-bg-elevated theme-text-secondary'}`}>
                  Existing Note
                </button>
              </div>
              {saveNoteTarget === 'new' ? (
                <input value={newNoteTitle} onChange={(e) => setNewNoteTitle(e.target.value)}
                  placeholder="Note title..." className="w-full p-2.5 rounded-lg border theme-border theme-bg-app text-[12px] outline-none" />
              ) : (
                <select value={saveNoteTarget} onChange={(e) => setSaveNoteTarget(e.target.value)}
                  className="w-full p-2.5 rounded-lg border theme-border theme-bg-app text-[12px] outline-none">
                  {notes.map(n => <option key={n.id} value={n.id}>{n.title}</option>)}
                </select>
              )}
              <button onClick={handleSaveAiToNote}
                className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12px] font-semibold transition-colors">
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="theme-bg-surface w-full max-w-sm rounded-2xl border theme-border shadow-xl p-5 space-y-4">
            <h3 className="text-[14px] font-bold text-red-600">
              {resetMode === 'clear' ? 'Clear Workspace?' : 'Reset Demo Data?'}
            </h3>
            <p className="text-[12px] theme-text-secondary leading-relaxed">
              {resetMode === 'clear'
                ? 'This clears your selections and AI results. Documents and notes are preserved.'
                : 'This will replace current data with demo research papers and notes.'}
            </p>
            <div className="flex gap-2">
              <button onClick={() => setShowResetConfirm(false)}
                className="flex-1 py-2 rounded-lg border theme-border text-[12px] font-semibold hover:theme-bg-elevated transition-colors">
                Cancel
              </button>
              <button onClick={async () => {
                try {
                  await (resetMode === 'clear' ? handleResetWorkspace() : handleResetDemoData());
                } catch (err) { alert(err.message); }
              }}
                className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-[12px] font-semibold transition-colors">
                {resetMode === 'clear' ? 'Clear' : 'Reset'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* CONFIRM DELETE MODAL                                             */}
      {/* ================================================================ */}
      {deleteModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="theme-bg-surface w-full max-w-sm rounded-2xl border theme-border shadow-xl p-5 space-y-4">
            <h3 className="text-[14px] font-bold text-red-600">
              Delete {deleteModal.type === 'document' ? 'Document' : 'Note'}?
            </h3>
            <p className="text-[12px] theme-text-secondary leading-relaxed">
              Are you sure you want to delete <strong>{deleteModal.item?.title}</strong>?
              {deleteModal.type === 'document' && ' Related analysis and extracted data will also be removed.'}
              {' '}This action cannot be undone.
            </p>
            {deleteModal.error && (
              <div className="p-2.5 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-[11px] text-red-700 dark:text-red-300">
                {deleteModal.error}
                <button onClick={() => setDeleteModal(prev => ({ ...prev, error: null }))} className="ml-2 underline font-semibold">Dismiss</button>
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={() => setDeleteModal({ open: false, type: null, item: null })}
                disabled={deleteLoading}
                className="flex-1 py-2 rounded-lg border theme-border text-[12px] font-semibold hover:theme-bg-elevated transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button
                onClick={async () => {
                  try {
                    if (deleteModal.type === 'document') {
                      await handleDeleteDocument(deleteModal.item.id);
                    } else {
                      await handleDeleteNote(deleteModal.item.id);
                    }
                  } catch (err) {
                    setDeleteModal(prev => ({ ...prev, error: err.message }));
                  }
                }}
                disabled={deleteLoading}
                className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-[12px] font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {deleteLoading && <span className="w-1.5 h-1.5 border-[1.5px] border-current border-t-transparent rounded-full animate-spin" />}
                {deleteLoading ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* RENAME MODAL                                                     */}
      {/* ================================================================ */}
      {renameModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="theme-bg-surface w-full max-w-sm rounded-2xl border theme-border shadow-xl p-5 space-y-4">
            <h3 className="text-[14px] font-bold theme-text-primary">
              Rename {renameModal.type === 'document' ? 'Document' : 'Note'}
            </h3>
            <input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && renameValue.trim()) { renameModal.type === 'document' ? handleRenameDocument(renameModal.item.id) : handleRenameNote(renameModal.item.id); } }}
              autoFocus
              className="w-full p-2.5 rounded-lg border theme-border theme-bg-app text-[12px] outline-none focus:border-indigo-500"
              placeholder="Enter new name..."
            />
            {renameModal.error && (
              <div className="p-2.5 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-[11px] text-red-700 dark:text-red-300">
                {renameModal.error}
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={() => setRenameModal({ open: false, type: null, item: null })}
                disabled={renameLoading}
                className="flex-1 py-2 rounded-lg border theme-border text-[12px] font-semibold hover:theme-bg-elevated transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button
                onClick={() => renameModal.type === 'document' ? handleRenameDocument(renameModal.item.id) : handleRenameNote(renameModal.item.id)}
                disabled={renameLoading || !renameValue.trim()}
                className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[12px] font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {renameLoading && <span className="w-1.5 h-1.5 border-[1.5px] border-current border-t-transparent rounded-full animate-spin" />}
                {renameLoading ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* SEARCH MODAL                                                     */}
      {/* ================================================================ */}
      {searchModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/40 backdrop-blur-sm p-4" onClick={() => setSearchModal(false)}>
          <div className="theme-bg-surface w-full max-w-lg rounded-2xl border theme-border shadow-xl overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 border-b theme-border">
              <Search size={16} className="theme-text-muted shrink-0" />
              <input
                ref={searchInputRef}
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                autoFocus
                placeholder="Search documents, notes, entities..."
                className="flex-1 bg-transparent outline-none text-[13px] theme-text-primary"
              />
              <kbd className="text-[9px] px-1.5 py-0.5 rounded border theme-border theme-text-muted font-mono">ESC</kbd>
            </div>
            <div className="max-h-[50vh] overflow-y-auto p-2">
              {searchLoading ? (
                <div className="py-8 text-center text-[12px] theme-text-muted">
                  <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" />
                  <span className="ml-2">Searching...</span>
                </div>
              ) : (searchResults.documents.length === 0 && searchResults.notes.length === 0 && searchResults.entities.length === 0) ? (
                <div className="py-8 text-center text-[12px] theme-text-muted">
                  {searchQuery ? 'No results found.' : 'Type to search across your research.'}
                </div>
              ) : (
                <div className="space-y-1">
                  {searchResults.documents.length > 0 && (
                    <div>
                      <div className="px-3 py-1 text-[9px] font-bold uppercase tracking-wider theme-text-muted">Documents</div>
                      {searchResults.documents.map(doc => (
                        <button key={doc.id} onClick={() => { setSelectedDocId(doc.id); setActiveView('document'); setDocTab('overview'); setSearchModal(false); }}
                          className="w-full text-left px-3 py-2 rounded-lg hover:theme-bg-elevated flex items-center gap-2.5 transition-colors">
                          <FileText size={14} className="text-indigo-500 shrink-0" />
                          <div className="min-w-0">
                            <div className="text-[12px] font-semibold theme-text-primary truncate">{doc.title}</div>
                            {doc.department && <div className="text-[10px] theme-text-muted truncate">{doc.department}</div>}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                  {searchResults.notes.length > 0 && (
                    <div>
                      <div className="px-3 py-1 text-[9px] font-bold uppercase tracking-wider theme-text-muted">Notes</div>
                      {searchResults.notes.map(note => (
                        <button key={note.id} onClick={() => { setSelectedNoteId(note.id); setActiveView('note'); setSearchModal(false); }}
                          className="w-full text-left px-3 py-2 rounded-lg hover:theme-bg-elevated flex items-center gap-2.5 transition-colors">
                          <Edit3 size={14} className="text-emerald-500 shrink-0" />
                          <div className="min-w-0">
                            <div className="text-[12px] font-semibold theme-text-primary truncate">{note.title}</div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                  {searchResults.entities.length > 0 && (
                    <div>
                      <div className="px-3 py-1 text-[9px] font-bold uppercase tracking-wider theme-text-muted">Entities</div>
                      {searchResults.entities.slice(0, 8).map((ent, i) => {
                        const id = ent.id || `ent_${i}`;
                        const name = ent.name || ent.title || '';
                        const type = ent.entity_type || ent.type || '';
                        return (
                          <button key={id} onClick={() => { setFocusGraphNodeId(id); setActiveView('graph'); setSearchModal(false); }}
                            className="w-full text-left px-3 py-2 rounded-lg hover:theme-bg-elevated flex items-center gap-2.5 transition-colors">
                            <Hash size={14} className="text-amber-500 shrink-0" />
                            <div className="min-w-0">
                              <div className="text-[12px] font-semibold theme-text-primary truncate">{name}</div>
                              {type && <div className="text-[10px] theme-text-muted uppercase">{type}</div>}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);

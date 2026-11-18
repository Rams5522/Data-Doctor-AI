import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Search,
  Filter,
  Plus,
  X,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Tag,
  Clock,
  Sparkles,
  ExternalLink
} from 'lucide-react';

const categoryMeta = [
  { id: 'data_quality', name: 'Data Quality', icon: '🔍', color: '#3b82f6' },
  { id: 'repair_strategies', name: 'Repair Strategies', icon: '🔧', color: '#22c55e' },
  { id: 'best_practices', name: 'Best Practices', icon: '✨', color: '#a855f7' },
  { id: 'case_studies', name: 'Case Studies', icon: '📚', color: '#f59e0b' }
];

const defaultTags = [
  'missing_values', 'imputation', 'duplicates', 'deduplication',
  'categorical', 'standardization', 'dates', 'parsing',
  'outliers', 'anomalies', 'types', 'conversion',
  'business_rules', 'validation', 'cleaning', 'normalization'
];

const KnowledgeBasePage = () => {
  const [articles, setArticles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', content: '', category: 'data_quality', tags: '' });
  const [activeTagFilter, setActiveTagFilter] = useState(null);
  const [sortBy, setSortBy] = useState('relevance');

  const filteredArticles = useMemo(() => {
    let result = [...articles];
    if (activeTagFilter) {
      result = result.filter(a => a.tags?.includes(activeTagFilter));
    }
    if (sortBy === 'recent') {
      result.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    } else if (sortBy === 'oldest') {
      result.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    } else if (sortBy === 'title') {
      result.sort((a, b) => a.title.localeCompare(b.title));
    }
    return result;
  }, [articles, activeTagFilter, sortBy]);

  const allTags = useMemo(() => {
    const tagSet = new Set();
    articles.forEach(a => a.tags?.forEach(t => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [articles]);

  const categoryStats = useMemo(() => {
    const stats = {};
    articles.forEach(a => {
      stats[a.category] = (stats[a.category] || 0) + 1;
    });
    return stats;
  }, [articles]);

  useEffect(() => {
    loadInitial();
  }, []);

  const loadInitial = async () => {
    setLoading(true);
    setError(null);
    try {
      const [catRes, searchRes] = await Promise.all([
        axios.get('/api/knowledge-base/categories'),
        axios.get('/api/knowledge-base/articles', { params: { query: 'data quality', limit: 50, min_similarity: 0.0 } })
      ]);
      setCategories(catRes.data.categories || []);
      setArticles(searchRes.data || []);
    } catch (err) {
      setError('Could not load the knowledge base. Is the backend running?');
      setCategories([]);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  };

  const runSearch = async (e) => {
    if (e) e.preventDefault();
    const query = searchTerm.trim() || 'data quality';
    setSearching(true);
    setError(null);
    try {
      const response = await axios.get('/api/knowledge-base/articles', {
        params: {
          query,
          category: selectedCategory === 'all' ? undefined : selectedCategory,
          limit: 50,
          min_similarity: searchTerm.trim() ? 0.25 : 0.0
        }
      });
      setArticles(response.data || []);
      setSelectedArticle(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const openArticle = async (article) => {
    try {
      const response = await axios.get(`/api/knowledge-base/articles/${article.id}`);
      setSelectedArticle(response.data);
    } catch {
      setSelectedArticle(article);
    }
  };

  const initializeDefaults = async () => {
    setInitializing(true);
    setError(null);
    try {
      await axios.post('/api/knowledge-base/initialize');
      await loadInitial();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to initialize knowledge base');
    } finally {
      setInitializing(false);
    }
  };

  const createArticle = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await axios.post('/api/knowledge-base/articles', {
        title: form.title,
        content: form.content,
        category: form.category,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean)
      });
      setForm({ title: '', content: '', category: 'data_quality', tags: '' });
      setShowCreate(false);
      await loadInitial();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create article');
    }
  };

  const handleTagClick = (tag) => {
    setActiveTagFilter(activeTagFilter === tag ? null : tag);
  };

  const clearFilters = () => {
    setActiveTagFilter(null);
    setSelectedCategory('all');
    setSearchTerm('');
    runSearch();
  };

  if (loading) {
    return (
      <div className="kb-page">
        <div className="kb-header">
          <div className="kb-header-left">
            <div className="header-badge"><span>📚</span> KNOWLEDGE BASE</div>
            <h1>Knowledge Base</h1>
            <p>Semantic search over data quality patterns, repair strategies, and best practices</p>
          </div>
        </div>
        <div className="kb-loading">
          <div className="empty-sparkle-box">📚</div>
          <h3>Loading Knowledge Base…</h3>
          <p>Fetching articles and categories.</p>
        </div>
      </div>
    );
  }

  const hasFilters = activeTagFilter || selectedCategory !== 'all' || searchTerm;

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div className="kb-header-left">
          <div className="header-badge"><span>📚</span> KNOWLEDGE BASE</div>
          <h1>Knowledge Base</h1>
          <p>Semantic search over data quality patterns, repair strategies, and best practices</p>
        </div>
        <div className="kb-header-right">
          <button className="primary-button" onClick={() => setShowCreate(true)}>
            <Plus size={18} /> Add Article
          </button>
          <button className="outline-button" onClick={initializeDefaults} disabled={initializing}>
            <Sparkles size={18} /> {initializing ? 'Initializing…' : 'Load Defaults'}
          </button>
        </div>
      </div>

      {error && (
        <div className="kb-alert error">
          <span>⚠️</span> {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Search & Filter Bar */}
      <section className="kb-search-section">
        <form onSubmit={runSearch} className="kb-search-form">
          <div className="kb-search-input-wrapper">
            <Search size={20} className="kb-search-icon" />
            <input
              type="text"
              className="kb-search-input"
              placeholder="Search by meaning… e.g. how to fill missing salaries"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              autoFocus
            />
          </div>

          <div className="kb-filter-group">
            <select
              className="kb-filter-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
            >
              <option value="all">All Categories</option>
              {categoryMeta.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>

            <select
              className="kb-filter-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="relevance">Relevance</option>
              <option value="recent">Most Recent</option>
              <option value="oldest">Oldest First</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>

          <button type="submit" className="primary-button" disabled={searching}>
            {searching ? 'Searching…' : 'Search'}
          </button>
        </form>

        {hasFilters && (
          <div className="kb-active-filters">
            {activeTagFilter && (
              <span className="kb-filter-tag">
                <Tag size={14} /> {activeTagFilter}
                <button onClick={() => setActiveTagFilter(null)}>✕</button>
              </span>
            )}
            {selectedCategory !== 'all' && (
              <span className="kb-filter-tag">
                <Filter size={14} /> {categoryMeta.find(c => c.id === selectedCategory)?.name}
                <button onClick={() => setSelectedCategory('all')}>✕</button>
              </span>
            )}
            {searchTerm && (
              <span className="kb-filter-tag">
                <Search size={14} /> "{searchTerm}"
                <button onClick={() => { setSearchTerm(''); runSearch(); }}>✕</button>
              </span>
            )}
            {(activeTagFilter || selectedCategory !== 'all' || searchTerm) && (
              <button className="kb-clear-filters" onClick={clearFilters}>
                Clear all
              </button>
            )}
          </div>
        )}
      </section>

      {/* Category Quick Stats */}
      <section className="kb-category-stats">
        {categoryMeta.map(cat => {
          const count = categoryStats[cat.id] || 0;
          const isActive = selectedCategory === cat.id;
          return (
            <button
              key={cat.id}
              className={`kb-category-card ${isActive ? 'active' : ''}`}
              onClick={() => setSelectedCategory(isActive ? 'all' : cat.id)}
              style={{ borderColor: isActive ? cat.color : undefined }}
            >
              <span className="kb-category-icon" style={{ background: cat.color }}>{cat.icon}</span>
              <div className="kb-category-info">
                <span className="kb-category-name">{cat.name}</span>
                <span className="kb-category-count">{count} articles</span>
              </div>
              {isActive && <ChevronUp size={16} className="kb-category-chevron" />}
            </button>
          );
        })}
      </section>

      {/* Tag Cloud Filter */}
      {allTags.length > 0 && (
        <section className="kb-tag-cloud">
          <div className="kb-tag-cloud-header">
            <h3>Popular Tags</h3>
            {activeTagFilter && (
              <button className="kb-tag-clear" onClick={() => setActiveTagFilter(null)}>
                Clear tag filter
              </button>
            )}
          </div>
          <div className="kb-tags">
            {allTags.slice(0, 24).map(tag => (
              <button
                key={tag}
                className={`kb-tag ${activeTagFilter === tag ? 'active' : ''}`}
                onClick={() => handleTagClick(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Article Detail Modal */}
      {selectedArticle && (
        <div className="kb-modal-overlay" onClick={() => setSelectedArticle(null)}>
          <div className="kb-modal" onClick={e => e.stopPropagation()}>
            <div className="kb-modal-header">
              <div>
                <span className="kb-modal-category">{selectedArticle.category.replace('_', ' ')}</span>
                <h2>{selectedArticle.title}</h2>
              </div>
              <button className="kb-modal-close" onClick={() => setSelectedArticle(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="kb-modal-body">
              <div className="kb-modal-meta">
                {selectedArticle.similarity != null && (
                  <span className="kb-similarity-badge">
                    <Sparkles size={14} /> Relevance: {(selectedArticle.similarity * 100).toFixed(0)}%
                  </span>
                )}
                <span className="kb-date">
                  <Clock size={14} /> Updated {new Date(selectedArticle.updated_at).toLocaleDateString()}
                </span>
              </div>
              <div className="kb-modal-tags">
                {selectedArticle.tags?.map(tag => (
                  <span key={tag} className="kb-tag-small">{tag}</span>
                ))}
              </div>
              <div className="kb-modal-content" style={{ whiteSpace: 'pre-wrap' }}>
                {selectedArticle.content}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Article Modal */}
      {showCreate && (
        <div className="kb-modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="kb-modal kb-modal-lg" onClick={e => e.stopPropagation()}>
            <div className="kb-modal-header">
              <h2>Create Article</h2>
              <button className="kb-modal-close" onClick={() => setShowCreate(false)}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={createArticle} className="kb-create-form">
              <div className="kb-form-field">
                <label>Title</label>
                <input
                  type="text"
                  className="quality-input"
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Handling Missing Values in Numerical Columns"
                />
              </div>
              <div className="kb-form-field">
                <label>Category</label>
                <select
                  className="quality-select"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  {categoryMeta.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="kb-form-field">
                <label>Content (Markdown supported)</label>
                <textarea
                  className="quality-input"
                  rows={10}
                  required
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  placeholder="Write your article content here…"
                />
              </div>
              <div className="kb-form-field">
                <label>Tags (comma separated)</label>
                <input
                  type="text"
                  className="quality-input"
                  value={form.tags}
                  onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  placeholder="missing_values, imputation, numerical"
                />
                <div className="kb-tag-suggestions">
                  {defaultTags.slice(0, 10).map(tag => (
                    <button
                      type="button"
                      key={tag}
                      className={`kb-tag-suggestion ${form.tags.includes(tag) ? 'added' : ''}`}
                      onClick={() => {
                        const tags = form.tags.split(',').map(t => t.trim()).filter(Boolean);
                        if (tags.includes(tag)) {
                          setForm({ ...form, tags: tags.filter(t => t !== tag).join(', ') });
                        } else {
                          setForm({ ...form, tags: [...tags, tag].join(', ') });
                        }
                      }}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
              <div className="kb-form-actions">
                <button type="button" className="outline-button" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary-button">
                  <Plus size={18} /> Save Article
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Articles Grid */}
      <section className="kb-results-section">
        <div className="kb-results-header">
          <h3>
            {filteredArticles.length === 1 ? '1 article' : `${filteredArticles.length} articles`}
            {selectedCategory !== 'all' && (
              <span> in {categoryMeta.find(c => c.id === selectedCategory)?.name}</span>
            )}
          </h3>
        </div>

        {filteredArticles.length === 0 ? (
          <div className="kb-empty">
            <div className="empty-sparkle-box">📭</div>
            <h3>No articles found</h3>
            <p>Try adjusting your search or filters, or load the default articles to get started.</p>
            <button className="primary-button" onClick={initializeDefaults} disabled={initializing}>
              <Sparkles size={18} /> Load Default Articles
            </button>
          </div>
        ) : (
          <div className="kb-articles-grid">
            {filteredArticles.map(article => {
              const catMeta = categoryMeta.find(c => c.id === article.category);
              return (
                <article key={article.id} className="kb-article-card">
                  <div className="kb-article-header">
                    <span className="kb-article-category" style={{ background: catMeta?.color || '#64748b' }}>
                      {catMeta?.icon || '📄'}
                    </span>
                    {article.similarity != null && (
                      <span className="kb-article-similarity">
                        <Sparkles size={12} /> {(article.similarity * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <h3 className="kb-article-title">{article.title}</h3>
                  <div className="kb-article-tags">
                    {article.tags?.slice(0, 3).map(tag => (
                      <span key={tag} className="kb-tag-small">{tag}</span>
                    ))}
                    {article.tags && article.tags.length > 3 && (
                      <span className="kb-tag-more">+{article.tags.length - 3}</span>
                    )}
                  </div>
                  <div className="kb-article-meta">
                    <span><Clock size={14} /> {new Date(article.updated_at).toLocaleDateString()}</span>
                  </div>
                  <button className="kb-read-more" onClick={() => openArticle(article)}>
                    Read more <ChevronRight size={14} />
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

const ChevronRight = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path d="M5 12h14M12 5l7 7-7 7" />
  </svg>
);

export default KnowledgeBasePage;
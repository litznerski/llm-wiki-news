/**
 * Knowledge Lab :: Chainlit UI Enhancement & Ergonomics Script
 * - Enforces side-view staying closed by default and across incoming messages.
 * - Opens ONLY when learner explicitly clicks on an element link in a message or top toggle.
 * - Injects branded Ambient Studio Status header inside Chainlit's top header.
 * - Renders Mermaid diagrams as live interactive SVGs with dark/light theme awareness.
 * - Unescapes branding HTML tags in Welcome message and chat responses.
 * - Suppresses third-party browser extension errors (e.g. FIDO2 CredentialsContainer).
 */

(function () {
  // 1. Proactively make navigator.credentials.create writable to prevent FIDO2 extension crash
  try {
    if (window.navigator && window.navigator.credentials) {
      const creds = window.navigator.credentials;
      const proto = Object.getPrototypeOf(creds);
      if (proto && Object.getOwnPropertyDescriptor(proto, "create")?.writable === false) {
        Object.defineProperty(creds, "create", {
          writable: true,
          configurable: true,
          value: proto.create ? proto.create.bind(creds) : function () {}
        });
      }
    }
  } catch (_) {}

  // Suppress browser extension injection errors via error, unhandledrejection, and window.onerror
  const prevOnError = window.onerror;
  window.onerror = function (msg, source, lineno, colno, error) {
    const errorStr = (String(msg || "") + " " + String(source || "")).toLowerCase();
    if (
      errorStr.includes("credentialscontainer") ||
      errorStr.includes("fido2") ||
      errorStr.includes("cannot assign to read only property")
    ) {
      return true;
    }
    if (typeof prevOnError === "function") {
      return prevOnError.apply(this, arguments);
    }
    return false;
  };

  window.addEventListener(
    "error",
    (e) => {
      const msg = String(e.message || "");
      if (
        msg.includes("CredentialsContainer") ||
        msg.includes("fido2-page-script") ||
        msg.includes("Cannot assign to read only property")
      ) {
        e.stopImmediatePropagation();
        e.preventDefault();
        return true;
      }
    },
    true
  );

  window.addEventListener(
    "unhandledrejection",
    (e) => {
      const reason = String(e.reason || "");
      if (
        reason.includes("CredentialsContainer") ||
        reason.includes("fido2-page-script") ||
        reason.includes("Cannot assign to read only property")
      ) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    },
    true
  );

  // 2. Intercept and filter known upstream Radix UI accessibility & MIME warnings
  const originalWarn = console.warn;
  const originalError = console.error;
  const RADIX_DIALOG_TITLE_MSG = "DialogContent requires a DialogTitle";

  console.warn = function (...args) {
    if (
      args.some(
        (arg) =>
          typeof arg === "string" &&
          (arg.includes(RADIX_DIALOG_TITLE_MSG) ||
            arg.includes('Skipped "application/*"') ||
            arg.includes("not a valid MIME type"))
      )
    ) {
      return;
    }
    originalWarn.apply(console, args);
  };
  console.error = function (...args) {
    if (
      args.some(
        (arg) =>
          typeof arg === "string" &&
          (arg.includes(RADIX_DIALOG_TITLE_MSG) ||
            arg.includes("CredentialsContainer") ||
            arg.includes("fido2-page-script") ||
            arg.includes("Cannot assign to read only property"))
      )
    ) {
      return;
    }
    originalError.apply(console, args);
  };

  let reopenBtn = null;
  let userExplicitlyOpened = false;
  let devTraceEverOpened = false;
  let cachedLastElement = null;

  let mermaidLoaded = false;
  let mermaidLoadingPromise = null;
  let mermaidRenderCounter = 0;
  let currentTheme = document.documentElement.classList.contains("light") ? "light" : "dark";

  const MERMAID_KEYWORDS = /^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram-v2|stateDiagram|erDiagram|gantt|pie|gitGraph|xychart-beta)\b/m;

  /**
   * Ensures the local vendor asset /public/mermaid.min.js is loaded and initialized.
   */
  function ensureMermaidLoaded() {
    if (window.mermaid) {
      mermaidLoaded = true;
      return Promise.resolve(window.mermaid);
    }
    if (mermaidLoadingPromise) return mermaidLoadingPromise;

    mermaidLoadingPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[src*="mermaid.min.js"]');
      if (existing) {
        existing.addEventListener("load", () => {
          mermaidLoaded = true;
          configureMermaid();
          resolve(window.mermaid);
        });
        existing.addEventListener("error", reject);
        return;
      }

      const script = document.createElement("script");
      script.src = "/public/mermaid.min.js";
      script.async = true;
      script.onload = () => {
        mermaidLoaded = true;
        configureMermaid();
        console.log("Knowledge Lab: Mermaid.js vendor script loaded successfully");
        resolve(window.mermaid);
      };
      script.onerror = (err) => {
        console.error("Knowledge Lab: Failed to load /public/mermaid.min.js", err);
        reject(err);
      };
      document.head.appendChild(script);
    });

    return mermaidLoadingPromise;
  }

  /**
   * Configures Mermaid with Knowledge Lab theme variables for light and dark modes.
   */
  function configureMermaid() {
    if (!window.mermaid) return;
    const isLight = document.documentElement.classList.contains("light");
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: isLight ? "default" : "dark",
      themeVariables: isLight
        ? {
            darkMode: false,
            background: "#ffffff",
            primaryColor: "#f1f5f9",
            primaryTextColor: "#0f172a",
            primaryBorderColor: "#ea580c",
            lineColor: "#c2410c",
            secondaryColor: "#e2e8f0",
            tertiaryColor: "#f8fafc"
          }
        : {
            darkMode: true,
            background: "#0f172a",
            primaryColor: "#1e293b",
            primaryTextColor: "#f8fafc",
            primaryBorderColor: "#f97316",
            lineColor: "#fdba74",
            secondaryColor: "#334155",
            tertiaryColor: "#1e293b"
          },
      fontFamily: "'JetBrains Mono', 'Poppins', monospace"
    });
  }

  /**
   * Scans chat messages for Mermaid code blocks and renders them into interactive SVG cards.
   */
  async function renderMermaidDiagrams() {
    await ensureMermaidLoaded();
    if (!window.mermaid) return;

    const candidates = Array.from(document.querySelectorAll("code.language-mermaid, pre code"));

    for (const codeEl of candidates) {
      if (codeEl.dataset.mermaidProcessed === "true") continue;
      if (codeEl.closest(".mermaid-diagram-card")) continue;

      const rawText = (codeEl.textContent || "").trim();
      const isMermaid =
        codeEl.classList.contains("language-mermaid") ||
        codeEl.className.includes("mermaid") ||
        MERMAID_KEYWORDS.test(rawText);

      if (!isMermaid || !rawText) continue;

      codeEl.dataset.mermaidProcessed = "true";

      const preEl = codeEl.closest("pre");
      const container = preEl ? (preEl.closest(".card, [class*='MuiCard']") || preEl) : codeEl;

      const cleanCode = rawText
        .replace(/&gt;/g, ">")
        .replace(/&lt;/g, "<")
        .replace(/&amp;/g, "&");

      const card = document.createElement("div");
      card.className = "mermaid-diagram-card";
      card.dataset.rawCode = cleanCode;

      const header = document.createElement("div");
      header.className = "mermaid-card-header";
      header.innerHTML = `
        <span class="mermaid-card-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/></svg>
          Mermaid Diagram
        </span>
        <div class="mermaid-card-actions">
          <button class="mermaid-btn-toggle" title="Toggle Code / Diagram">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>Code</span>
          </button>
          <button class="mermaid-btn-copy" title="Copy Mermaid Definition">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
            <span>Copy</span>
          </button>
        </div>
      `;

      const svgWrapper = document.createElement("div");
      svgWrapper.className = "mermaid-svg-wrapper";

      const codeWrapper = document.createElement("div");
      codeWrapper.className = "mermaid-raw-code-container";
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = cleanCode;
      pre.appendChild(code);
      codeWrapper.appendChild(pre);

      card.appendChild(header);
      card.appendChild(svgWrapper);
      card.appendChild(codeWrapper);

      // Interactive controls
      const toggleBtn = header.querySelector(".mermaid-btn-toggle");
      let showingCode = false;
      toggleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        showingCode = !showingCode;
        if (showingCode) {
          svgWrapper.style.display = "none";
          codeWrapper.style.display = "block";
          toggleBtn.querySelector("span").textContent = "Diagram";
        } else {
          svgWrapper.style.display = "flex";
          codeWrapper.style.display = "none";
          toggleBtn.querySelector("span").textContent = "Code";
        }
      });

      const copyBtn = header.querySelector(".mermaid-btn-copy");
      copyBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        try {
          await navigator.clipboard.writeText(cleanCode);
          const span = copyBtn.querySelector("span");
          const orig = span.textContent;
          span.textContent = "Copied!";
          setTimeout(() => { span.textContent = orig; }, 1500);
        } catch (err) {
          console.error("Failed to copy", err);
        }
      });

      // Render SVG
      const diagId = "mermaid-svg-" + Date.now() + "-" + (++mermaidRenderCounter);
      try {
        const { svg } = await window.mermaid.render(diagId, cleanCode);
        svgWrapper.innerHTML = svg;

        // Hide raw code container and insert interactive diagram card
        container.style.display = "none";

        // Check if container is already inside a <details>
        const existingDetails = container.closest("details");
        if (existingDetails) {
          container.parentNode.insertBefore(card, container.nextSibling);
          if (!existingDetails.dataset.mermaidToggleBound) {
            existingDetails.dataset.mermaidToggleBound = "true";
            existingDetails.addEventListener("toggle", () => {
              window.dispatchEvent(new Event("resize"));
            });
          }
        } else {
          // Wrap inside collapsible container with default closed
          const details = document.createElement("details");
          details.className = "mermaid-collapsible-wrapper";
          const summary = document.createElement("summary");
          summary.innerHTML = "📊 Visual Architecture / Flowchart (Click to expand)";
          details.appendChild(summary);
          details.appendChild(card);
          container.parentNode.insertBefore(details, container.nextSibling);

          details.addEventListener("toggle", () => {
            window.dispatchEvent(new Event("resize"));
          });
        }
      } catch (err) {
        console.warn("Knowledge Lab: Mermaid render failure for block:", err);
        const lingering = document.querySelectorAll(`[id*="${diagId}"]`);
        lingering.forEach((el) => el.remove());
        codeEl.dataset.mermaidProcessed = "failed";
      }
    }
  }

  /**
   * Re-renders all rendered diagrams when switching between Light Mode and Dark Mode.
   */
  async function reRenderAllMermaidDiagrams() {
    if (!window.mermaid) return;
    configureMermaid();

    const cards = document.querySelectorAll(".mermaid-diagram-card");
    for (const card of cards) {
      const rawCode = card.dataset.rawCode;
      if (!rawCode) continue;

      const svgWrapper = card.querySelector(".mermaid-svg-wrapper");
      if (!svgWrapper) continue;

      const diagId = "mermaid-re-" + Date.now() + "-" + (++mermaidRenderCounter);
      try {
        const { svg } = await window.mermaid.render(diagId, rawCode);
        svgWrapper.innerHTML = svg;
      } catch (err) {
        console.warn("Knowledge Lab: Failed to re-render diagram on theme change:", err);
        const lingering = document.querySelectorAll(`[id*="${diagId}"]`);
        lingering.forEach((el) => el.remove());
      }
    }
  }

  /**
   * Unescapes brand HTML tags in case ReactMarkdown escaped them.
   */
  function fixEscapedHtmlInMessages() {
    const nodes = document.querySelectorAll(".message-content, [data-step-name]");
    for (const node of nodes) {
      if (
        node.innerHTML &&
        (node.innerHTML.includes('&lt;span class="brand-') ||
          node.innerHTML.includes('&lt;span class="font-'))
      ) {
        node.innerHTML = node.innerHTML
          .replace(/&lt;span class="([^"]+)"&gt;/g, '<span class="$1">')
          .replace(/&lt;\/span&gt;/g, "</span>");
      }
    }
  }

  const WIKILINK_IN_CHAT_REGEX = /\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]/g;

  /**
   * Determines the target Astro Wiki base URL depending on viewport context.
   * In embedded iframe mode or standalone on port 8080, routes to Astro port 4321 /wiki.
   */
  function getAstroWikiBaseUrl() {
    const isLocalhost8080 = window.location.port === "8080";
    if (isLocalhost8080) {
      return `${window.location.protocol}//${window.location.hostname}:4321/wiki`;
    }
    return "/wiki";
  }

  function slugifyChatWikilink(text) {
    if (!text) return "";
    return text
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim()
      .replace(/\s+/g, "-")
      .replace(/[^\w-]+/g, "")
      .replace(/--+/g, "-");
  }

  /**
   * Scans chat messages and transforms [[Concept Title]] into active hyperlinks opening in a new tab.
   * Invariant: target="_blank" with rel="noopener noreferrer" ensures ongoing chat state is never lost.
   */
  function renderChatWikilinks() {
    const messageBlocks = document.querySelectorAll(".message-content p, .message-content li, .step p, [data-step-name] p");
    const baseUrl = getAstroWikiBaseUrl();

    for (const block of messageBlocks) {
      if (block.dataset.wikilinksProcessed === "true") continue;
      if (block.closest("pre, code, a")) continue;
      if (!block.innerHTML.includes("[[")) continue;

      block.dataset.wikilinksProcessed = "true";

      block.innerHTML = block.innerHTML.replace(WIKILINK_IN_CHAT_REGEX, (match, rawTarget, rawAnchor, rawAlias) => {
        const targetTitle = rawTarget.trim();
        const targetLeaf = targetTitle.split("/").pop() || targetTitle;
        const slug = slugifyChatWikilink(targetLeaf);

        const isSourceOrPrivate = 
          targetTitle.toLowerCase().startsWith("sources/") || 
          targetTitle.toLowerCase().includes("/sources/") ||
          targetTitle.toLowerCase().startsWith("ingestions/") ||
          targetTitle.toLowerCase().includes("/ingestions/");

        const displayText = rawAlias 
          ? rawAlias.trim() 
          : (rawAnchor ? `${targetTitle} § ${rawAnchor.trim()}` : (isSourceOrPrivate ? targetLeaf : targetTitle));

        if (isSourceOrPrivate) {
          return `<span class="wiki-link-unresolved" title="Vault primitive (${targetTitle}) is retained internally"><span class="unresolved-icon">🔒</span>${displayText}</span>`;
        }

        const anchor = rawAnchor ? `#${slugifyChatWikilink(rawAnchor.trim())}` : "";
        const targetUrl = `${baseUrl}/${slug}${anchor}`;

        return `<a href="${targetUrl}" target="_blank" rel="noopener noreferrer" class="chainlit-published-wikilink" title="Open ${targetTitle} in Knowledge Lab Knowledge Wiki (New Tab)">
          <span class="wikilink-pill">
            <span class="wikilink-badge-icon">🏛️</span>
            <span class="wikilink-label">${displayText}</span>
            <svg class="wikilink-ext-icon" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </span>
        </a>`;
      });
    }
  }


  /**
   * Searches the DOM or React Fiber for the latest element to re-open the side panel.
   */
  function reopenSideView() {
    userExplicitlyOpened = true;

    // 1. Primary Strategy: Find the latest element link in chat messages (prioritizing dev trace if devTraceEverOpened).
    const elementLinks = Array.from(
      document.querySelectorAll("a.element-link, .element-link, [data-element-id]")
    );

    if (devTraceEverOpened) {
      const devLinks = elementLinks.filter((l) => {
        const text = (l.textContent || "").toLowerCase();
        return text.includes("dev") || text.includes("trace") || text.includes("fastmcp");
      });
      if (devLinks.length > 0) {
        const target = devLinks[devLinks.length - 1];
        target.click();
        target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
        return true;
      }
    }

    if (elementLinks.length > 0) {
      const target = elementLinks[elementLinks.length - 1];
      target.click();
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      return true;
    }

    // 2. React Fiber Strategy: Access MessageContext.onElementRefClick from DOM fiber
    const walkerNodes = Array.from(document.querySelectorAll(".message-content, .step, #root"));
    for (const node of walkerNodes) {
      const fiberKey = Object.keys(node).find(
        (k) => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$")
      );
      if (!fiberKey) continue;

      let fiber = node[fiberKey];
      while (fiber) {
        const ctx = fiber.memoizedProps?.value;
        if (ctx && typeof ctx.onElementRefClick === "function") {
          if (cachedLastElement) {
            ctx.onElementRefClick(cachedLastElement);
            return true;
          }

          let child = fiber;
          let foundElements = null;
          for (let i = 0; i < 15 && child; i++) {
            if (Array.isArray(child.memoizedProps?.elements) && child.memoizedProps.elements.length > 0) {
              foundElements = child.memoizedProps.elements;
              break;
            }
            child = child.child;
          }

          if (foundElements && foundElements.length > 0) {
            const lastElem = foundElements[foundElements.length - 1];
            ctx.onElementRefClick(lastElem);
            return true;
          }
        }
        fiber = fiber.return;
      }
    }

    // 3. Fallback: Any clickable element matching keywords
    const candidateButtons = Array.from(document.querySelectorAll("button, a")).filter((b) => {
      const text = (b.textContent || "").toLowerCase();
      return (
        text.includes("inspector") ||
        text.includes("active valves") ||
        text.includes("arcadedb") ||
        text.includes("dev") ||
        text.includes("trace")
      );
    });

    if (candidateButtons.length > 0) {
      const target = candidateButtons[candidateButtons.length - 1];
      target.click();
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      return true;
    }

    return false;
  }

  function ensureReopenButton() {
    if (document.getElementById("reopen-sideview-btn")) {
      return document.getElementById("reopen-sideview-btn");
    }

    const btn = document.createElement("button");
    btn.id = "reopen-sideview-btn";
    btn.setAttribute("title", "Re-open Inspector & Valves panel");
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg><span>Inspector</span>`;
    btn.style.display = "none";

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      reopenSideView();
    });

    document.body.appendChild(btn);
    return btn;
  }

  /**
   * Injects the Ambient Studio Status header directly into Chainlit's top header.
   * Visible in both standalone (port 8080) and embedded iframe modes.
   */
  function ensureAmbientStudioHeader() {
    const header = document.getElementById("header");
    if (!header || document.getElementById("ambient-studio-header")) return;

    const statusDiv = document.createElement("div");
    statusDiv.id = "ambient-studio-header";
    statusDiv.className = "ambient-studio-header";
    statusDiv.innerHTML = `
      <div class="status-badge-container">
        <span class="status-pulse-dot"></span>
        <div class="brand-group">
          <span class="brand-knowledge-lab"><span class="brand-knowledge">knowledge</span><span class="brand-lab">lab</span></span>
          <span class="studio-subtext">Learning Studio</span>
        </div>
        <span class="engine-badge">ArcadeDB Connected</span>
        <div class="meta-pills">
          <span class="meta-label">Graph: <span class="meta-val">knowledgedb</span></span>
          <span class="meta-sep">•</span>
          <span class="meta-label">Middleware: <span class="meta-val">FastMCP</span></span>
        </div>
      </div>
    `;

    header.appendChild(statusDiv);
  }

  let lastScrolledTurnNum = null;

  const CALLOUT_CONFIGS = {
    note: { title: "Note", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>' },
    tip: { title: "Tip", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>' },
    important: { title: "Important", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' },
    warning: { title: "Warning", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' },
    caution: { title: "Caution", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' },
    danger: { title: "Danger", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' },
    example: { title: "Example", icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><polyline points="10 2 10 10 13 7 16 10 16 2"/></svg>' }
  };

  const CALLOUT_REGEX = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|DANGER|EXAMPLE|INFO|QUESTION|QUOTE)\](?:\s*([^\n<]*))?/i;
  const CALLOUT_STRIP_REGEX = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|DANGER|EXAMPLE|INFO|QUESTION|QUOTE)\](?:\s*[^\n<]*)?(?:<br\s*\/?>|\n)?/i;

  /**
   * Transforms markdown blockquotes with [!TYPE] syntax into styled Obsidian/GitHub callouts.
   * Strips the [!TYPE] syntax token and title from the body prose so it only appears in the header.
   */
  function processCallouts() {
    const blockquotes = document.querySelectorAll("blockquote:not([data-callout-processed='true'])");
    for (const bq of blockquotes) {
      const rawText = (bq.textContent || "").trim();
      const match = rawText.match(CALLOUT_REGEX);
      if (!match) continue;

      bq.dataset.calloutProcessed = "true";
      const typeKey = match[1].toLowerCase();
      const config = CALLOUT_CONFIGS[typeKey] || CALLOUT_CONFIGS.note;
      const rawTitle = (match[2] || "").trim();
      const title = rawTitle || config.title;

      // Clean the [!TYPE] token and title from the first paragraph or text nodes
      let stripped = false;
      const paragraphs = bq.querySelectorAll("p");
      if (paragraphs.length > 0) {
        for (const p of paragraphs) {
          if (CALLOUT_REGEX.test(p.textContent)) {
            p.innerHTML = p.innerHTML.replace(CALLOUT_STRIP_REGEX, "").trim();
            if (!p.innerHTML || p.innerHTML === "") {
              p.remove();
            }
            stripped = true;
            break;
          }
        }
      }

      if (!stripped) {
        const walker = document.createTreeWalker(bq, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while ((node = walker.nextNode())) {
          if (CALLOUT_REGEX.test(node.nodeValue)) {
            node.nodeValue = node.nodeValue.replace(/^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|DANGER|EXAMPLE|INFO|QUESTION|QUOTE)\](?:\s*[^\n]*)?/i, "").trim();
            stripped = true;
            break;
          }
        }
      }

      bq.classList.add("obsidian-callout", "callout-" + typeKey);

      const header = document.createElement("div");
      header.className = "obsidian-callout-header";
      header.innerHTML = `
        <span class="obsidian-callout-icon">${config.icon}</span>
        <span class="obsidian-callout-title">${title}</span>
      `;
      bq.prepend(header);
    }
  }

  /**
   * Deduplicates turn cards in developer sidebar so historical turns never appear twice.
   */
  function deduplicateDevTurns() {
    const sideContent = document.getElementById("side-view-content");
    if (!sideContent) return;
    const cards = Array.from(sideContent.querySelectorAll("details.dev-turn-card[data-turn-num]"));
    const seenTurns = new Set();
    // Traverse in reverse so the latest rendered copy is kept and older duplicates are removed
    for (let i = cards.length - 1; i >= 0; i--) {
      const card = cards[i];
      const turnNum = card.getAttribute("data-turn-num");
      if (turnNum) {
        if (seenTurns.has(turnNum)) {
          card.remove();
        } else {
          seenTurns.add(turnNum);
        }
      }
    }
  }

  /**
   * Automatically adds accessible DialogTitle to Radix UI / MUI dialogs missing title headers.
   */
  function ensureDialogTitles() {
    const dialogs = document.querySelectorAll('[role="dialog"], [data-radix-dialog-content]');
    dialogs.forEach((dialog) => {
      const hasTitle = dialog.querySelector('[data-radix-dialog-title], [id*="dialog-title"], h1, h2, h3');
      if (!hasTitle) {
        const titleId = "radix-auto-title-" + Math.random().toString(36).substring(2, 9);
        const title = document.createElement("h2");
        title.id = titleId;
        title.className = "sr-only";
        title.textContent = "Dialog";
        title.style.position = "absolute";
        title.style.width = "1px";
        title.style.height = "1px";
        title.style.padding = "0";
        title.style.margin = "-1px";
        title.style.overflow = "hidden";
        title.style.clip = "rect(0, 0, 0, 0)";
        title.style.whiteSpace = "nowrap";
        title.style.borderWidth = "0";
        dialog.prepend(title);
        if (!dialog.getAttribute("aria-labelledby")) {
          dialog.setAttribute("aria-labelledby", titleId);
        }
      }
    });
  }

  /**
   * Injects styling for collapsible developer turns inside the sidebar.
   */
  function injectDevSidebarStyles() {
    if (document.getElementById("dev-sidebar-custom-styles")) return;
    const style = document.createElement("style");
    style.id = "dev-sidebar-custom-styles";
    style.textContent = `
      details.dev-turn-card {
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 8px;
        margin-bottom: 12px;
        padding: 6px 12px 10px 12px;
        background: rgba(248, 250, 252, 0.6);
        transition: all 0.2s ease-in-out;
      }
      html.dark details.dev-turn-card {
        background: rgba(15, 23, 42, 0.45);
        border-color: rgba(71, 85, 105, 0.4);
      }
      details.dev-turn-card[open] {
        border-color: #ea580c;
        box-shadow: 0 2px 10px rgba(234, 88, 12, 0.08);
      }
      details.dev-turn-card summary {
        cursor: pointer;
        padding: 6px 0;
        font-size: 0.88rem;
        user-select: none;
        outline: none;
        list-style: revert;
      }
      details.dev-turn-card summary:hover {
        color: #ea580c;
      }
      details.dev-turn-card[open] summary {
        border-bottom: 1px dashed rgba(148, 163, 184, 0.3);
        margin-bottom: 10px;
        padding-bottom: 8px;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Smoothly auto-scrolls the sidebar to the latest turn card inside #side-view-content.
   * Keeps scrolling strictly contained within the sideContent viewport to prevent
   * moving the parent drawer or scrolling the header out of the window.
   */
  function autoScrollSidebar() {
    const sideContent = document.getElementById("side-view-content");
    if (!sideContent) return;

    const latestTurn = sideContent.querySelector("details.dev-turn-latest, details[open]:last-of-type, details.dev-turn-card:last-of-type");
    if (latestTurn) {
      const turnNum = latestTurn.getAttribute("data-turn-num");
      if (turnNum && turnNum !== lastScrolledTurnNum) {
        lastScrolledTurnNum = turnNum;
        setTimeout(() => {
          const targetY = latestTurn.offsetTop - sideContent.offsetTop;
          sideContent.scrollTo({ top: Math.max(0, targetY), behavior: "smooth" });
        }, 120);
      }
    }
  }

  /**
   * Monitors and synchronizes side-panel state, diagrams, and branding.
   * Invariant: Side-view MUST stay closed unless learner explicitly clicked an element link or toggle!
   */
  function syncSidebarState() {
    ensureAmbientStudioHeader();
    fixEscapedHtmlInMessages();
    renderChatWikilinks();
    processCallouts();
    ensureDialogTitles();
    deduplicateDevTurns();
    renderMermaidDiagrams();
    injectDevSidebarStyles();
    autoScrollSidebar();

    const sideContent = document.getElementById("side-view-content");
    const closeBtn = document.querySelector("#side-view-title button");
    const btn = ensureReopenButton();

    // Check if side panel title indicates a developer trace
    const titleEl = document.getElementById("side-view-title");
    const titleText = (titleEl?.textContent || "").toLowerCase();
    const isDevTrace = titleText.includes("dev") || titleText.includes("trace") || titleText.includes("developer");

    if (sideContent && isDevTrace) {
      devTraceEverOpened = true;
    }

    // Enforce static "Developer Trace" title in sidebar header (Chainlit Testing 6 requirement)
    if (sideContent && (isDevTrace || devTraceEverOpened) && titleEl) {
      const heading = titleEl.querySelector("h1, h2, h3, h4, h5, h6, span, div") || titleEl;
      if (heading) {
        const text = heading.textContent ? heading.textContent.trim() : "";
        if (text && text !== "Developer Trace" && (text.includes("Trace") || text.includes("Dev") || text.includes("Inspector") || text.includes("FastMCP"))) {
          heading.textContent = "Developer Trace";
        }
      }
    }

    // Auto-close side-panel ONLY if learner never opened it and it is neither a dev trace nor previously opened in dev mode!
    if (sideContent && closeBtn && !userExplicitlyOpened && !isDevTrace && !devTraceEverOpened) {
      closeBtn.click();
      return;
    }

    // If dev trace was opened, ensure it stays open across incoming turns
    if (devTraceEverOpened && !sideContent) {
      const devLinks = Array.from(document.querySelectorAll("a.element-link, .element-link")).filter((l) => {
        const text = (l.textContent || "").toLowerCase();
        return text.includes("dev") || text.includes("trace") || text.includes("fastmcp");
      });
      if (devLinks.length > 0) {
        const latestDevLink = devLinks[devLinks.length - 1];
        if (!latestDevLink.dataset.devAutoOpened) {
          latestDevLink.dataset.devAutoOpened = "true";
          userExplicitlyOpened = true;
          latestDevLink.click();
          latestDevLink.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
        }
      }
    }

    // Toggle floating reopen button visibility
    const hasElements =
      document.querySelectorAll("a.element-link, .element-link").length > 0 ||
      cachedLastElement !== null;

    if (!sideContent && hasElements) {
      btn.style.display = "inline-flex";
    } else {
      btn.style.display = "none";
    }

    // Cache element references from DOM links if available
    const links = document.querySelectorAll("a.element-link, .element-link");
    if (links.length > 0) {
      const lastLink = links[links.length - 1];
      const fiberKey = Object.keys(lastLink).find((k) => k.startsWith("__reactFiber$"));
      if (fiberKey && lastLink[fiberKey]?.memoizedProps?.element) {
        cachedLastElement = lastLink[fiberKey].memoizedProps.element;
      }
    }
  }

  // Intercept user interactions
  document.addEventListener(
    "click",
    (e) => {
      // User clicked close button on side panel
      if (e.target.closest("#side-view-title button, #side-view-title [aria-label*='close']")) {
        userExplicitlyOpened = false;
        devTraceEverOpened = false;
        setTimeout(safeSyncSidebarState, 50);
      }

      // User clicked an element link inside chat
      const clickedLink = e.target.closest("a.element-link, .element-link");
      if (clickedLink) {
        userExplicitlyOpened = true;
        const text = (clickedLink.textContent || "").toLowerCase();
        if (text.includes("dev") || text.includes("trace") || text.includes("fastmcp")) {
          devTraceEverOpened = true;
        }
        setTimeout(safeSyncSidebarState, 50);
      }

      // User clicked chat submit button
      if (e.target.closest("#chat-submit-button, button[type='submit']")) {
        if (!devTraceEverOpened) {
          userExplicitlyOpened = false;
        }
      }
    },
    true
  );

  // User pressed Enter to send message -> reset explicit open flag only if dev trace is not active!
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        const active = document.activeElement;
        if (active && (active.tagName === "TEXTAREA" || active.tagName === "INPUT")) {
          if (!devTraceEverOpened) {
            userExplicitlyOpened = false;
          }
        }
      }
    },
    true
  );

  // MutationObserver on document.documentElement to detect dark/light theme toggle
  const themeObserver = new MutationObserver(() => {
    const isLight = document.documentElement.classList.contains("light");
    const newTheme = isLight ? "light" : "dark";
    if (newTheme !== currentTheme) {
      currentTheme = newTheme;
      console.log(`Knowledge Lab: Theme toggled to ${newTheme}, re-rendering diagrams...`);
      reRenderAllMermaidDiagrams();
    }
  });

  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"]
  });

  // Re-entrancy guard & debouncing to completely eliminate infinite mutation loops (RESULT_CODE_HUNG)
  let isSyncing = false;
  let syncDebounceTimer = null;

  function safeSyncSidebarState() {
    if (isSyncing) return;
    isSyncing = true;
    try {
      syncSidebarState();
    } finally {
      isSyncing = false;
    }
  }

  function scheduleSyncSidebarState() {
    if (syncDebounceTimer) return;
    syncDebounceTimer = setTimeout(() => {
      syncDebounceTimer = null;
      safeSyncSidebarState();
    }, 60);
  }

  // MutationObserver for responsive state updates
  const bodyObserver = new MutationObserver((mutations) => {
    // Drop mutations originating from custom header or reopen button
    const isSelfMutation = mutations.every((m) => {
      const el = m.target.nodeType === Node.ELEMENT_NODE ? m.target : m.target.parentElement;
      return (
        el &&
        (el.closest("#reopen-sideview-btn") ||
         el.closest("#ambient-studio-header") ||
         el.closest(".dev-turn-card"))
      );
    });
  /* ==============================================================================
     13. URL Query Parameter & PostMessage Chat Input Population (?q=...)
     ============================================================================== */
  let inputQueryProcessed = false;

  function populateChatInput(text) {
    if (!text || inputQueryProcessed) return false;

    // Chainlit textareas: #chat-input, textarea[data-testid="chat-input"], or any textarea in footer/form
    const textarea = document.querySelector("#chat-input, textarea[data-testid='chat-input'], textarea");
    if (!textarea) return false;

    try {
      // Use React's prototype setter to ensure synthetic state updates
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      )?.set;

      if (nativeSetter) {
        nativeSetter.call(textarea, text);
      } else {
        textarea.value = text;
      }

      // Dispatch React input & change events
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
      textarea.focus();

      // Adjust height if autosize is applied
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";

      inputQueryProcessed = true;
      console.log("[knowledge-lab] Successfully populated chat input with query:", text);
      return true;
    } catch (e) {
      console.warn("[knowledge-lab] Failed to populate chat input:", e);
      return false;
    }
  }

  function checkUrlQueryPrompt() {
    if (inputQueryProcessed) return;
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const q = urlParams.get("q");
      if (q) {
        let attempts = 0;
        const interval = setInterval(() => {
          attempts++;
          if (populateChatInput(q) || attempts > 50) {
            clearInterval(interval);
          }
        }, 150);
      }
    } catch (_) {}
  }

  // Listen for postMessage from parent Astro container
  window.addEventListener("message", (event) => {
    if (event.data?.type === "CHAINLIT_SET_PROMPT" && event.data.query) {
      populateChatInput(event.data.query);
    }
  });

  checkUrlQueryPrompt();

  window.addEventListener("DOMContentLoaded", () => {
    ensureReopenButton();
    ensureAmbientStudioHeader();
    ensureMermaidLoaded();
    checkUrlQueryPrompt();
    bodyObserver.observe(document.body, { childList: true, subtree: true });
    safeSyncSidebarState();
  });

  // Periodic sync (guarded with safeSyncSidebarState)
  setInterval(safeSyncSidebarState, 1000);
})();

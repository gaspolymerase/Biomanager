import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableHeader from '@tiptap/extension-table-header';
import TableCell from '@tiptap/extension-table-cell';
import { Markdown } from 'tiptap-markdown';

import { MentionDecoration } from './extensions/MentionDecoration.js';
import { MentionSuggestion } from './extensions/MentionSuggestion.js';
import { createToolbar } from './toolbar.js';
import { attachTableAutofill } from './table-autofill.js';

import './styles.css';

function debounce(fn, delay) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

function uploadAndInsertImage(editor, file) {
  if (!file) return;
  const formData = new FormData();
  formData.append('image', file);
  return fetch('/notebook/upload-image', { method: 'POST', body: formData })
    .then((r) => r.json())
    .then((data) => {
      if (data && data.ok && data.url) {
        editor.chain().focus().setImage({ src: data.url, alt: 'image' }).run();
      }
    })
    .catch(() => {});
}

function formatBytes(n) {
  if (!n || n < 1024) return `${n || 0} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// Upload a non-image file. Inserts a markdown link styled as a "file chip" via
// the link's title attribute (we render file links specially in CSS based on
// the URL path containing "/static/uploads/" + non-image extension).
function uploadAndInsertFile(editor, file) {
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  return fetch('/notebook/upload-file', { method: 'POST', body: formData })
    .then((r) => r.json())
    .then((data) => {
      if (!data || !data.ok || !data.url) return;
      const label = `${data.name} (${formatBytes(data.size)})`;
      // Plain markdown link — round-trips cleanly through tiptap-markdown.
      // CSS targets .tiptap-editor-host a[href*="/static/uploads/"] for chip look.
      editor
        .chain()
        .focus()
        .insertContent(`[${label}](${data.url})`)
        .run();
    })
    .catch(() => {});
}

window.BiomanagerNotebookUpload = {
  image: uploadAndInsertImage,
  file: uploadAndInsertFile,
};

const PLACEHOLDER = 'Start writing… type @mouse 123, @plasmid 4, or @order 7 to reference. Drop a file or image to attach. Cmd/Ctrl+click a chip to follow it.';

window.BiomanagerNotebook = {
  mount({ element, initialMarkdown, onChange }) {
    const editor = new Editor({
      element,
      extensions: [
        StarterKit.configure({
          heading: { levels: [1, 2, 3, 4] },
          codeBlock: { HTMLAttributes: { class: 'tiptap-code-block' } },
        }),
        Markdown.configure({ html: false, linkify: true, breaks: true, transformCopiedText: true }),
        Placeholder.configure({
          placeholder: ({ node }) => (node.type.name === 'heading' ? `Heading ${node.attrs.level}` : PLACEHOLDER),
        }),
        Link.configure({ openOnClick: true, HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' } }),
        Image,
        TaskList,
        TaskItem.configure({ nested: true }),
        Table.configure({ resizable: true, HTMLAttributes: { class: 'tiptap-table' } }),
        TableRow,
        TableHeader,
        TableCell,
        MentionDecoration,
        MentionSuggestion,
      ],
      content: initialMarkdown || '',
      autofocus: !initialMarkdown,
      onUpdate({ editor }) {
        if (typeof onChange === 'function') {
          onChange(editor.storage.markdown.getMarkdown());
        }
      },
    });

    const debouncedSave = onChange ? debounce(onChange, 200) : null;
    editor.on('update', () => {
      if (debouncedSave) debouncedSave(editor.storage.markdown.getMarkdown());
    });

    element.addEventListener('paste', (event) => {
      if (!event.clipboardData) return;
      for (const item of event.clipboardData.items) {
        if (item.type && item.type.startsWith('image/')) {
          event.preventDefault();
          const file = item.getAsFile();
          if (file) uploadAndInsertImage(editor, file);
          return;
        }
      }
    });

    element.addEventListener('drop', (event) => {
      const files = event.dataTransfer && event.dataTransfer.files;
      if (!files || files.length === 0) return;
      const file = files[0];
      if (file.type && file.type.startsWith('image/')) {
        event.preventDefault();
        uploadAndInsertImage(editor, file);
      } else {
        event.preventDefault();
        uploadAndInsertFile(editor, file);
      }
    });

    const toolbar = createToolbar(editor);
    const autofill = attachTableAutofill(editor, element);

    return {
      editor,
      destroy: () => {
        autofill.destroy();
        toolbar.destroy();
        editor.destroy();
      },
      getMarkdown: () => editor.storage.markdown.getMarkdown(),
    };
  },
};

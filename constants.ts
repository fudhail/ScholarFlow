
import { Paper, ProjectFile } from './types';

// Virtual Project ID for Discovery Mode (when no project is open)
// This matches the backend constant and allows papers to be saved to a shared library
export const VIRTUAL_PROJECT_ID = "discovery-virtual-library";

// Using a stable sample PDF that allows CORS
const SAMPLE_PDF = "https://raw.githubusercontent.com/mozilla/pdf.js/ba2edeae/web/compressed.tracemonkey-pldi-09.pdf";

export const MOCK_PAPERS: Paper[] = [
  {
    id: 'p1',
    title: 'Attention Is All You Need',
    authors: ['Vaswani et al.'],
    year: 2017,
    summary: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...',
    tags: ['NLP', 'Transformer'],
    pdfUrl: SAMPLE_PDF
  },
  {
    id: 'p2',
    title: 'LoRA: Low-Rank Adaptation of Large Language Models',
    authors: ['Hu et al.'],
    year: 2021,
    summary: 'We propose Low-Rank Adaptation, or LoRA, which freezes the pre-trained model weights and injects trainable rank decomposition matrices...',
    tags: ['LLM', 'Fine-tuning'],
    pdfUrl: SAMPLE_PDF
  },
  {
    id: 'p3',
    title: 'Constitutional AI: Harmlessness from AI Feedback',
    authors: ['Bai et al.'],
    year: 2022,
    summary: 'We train a harmless AI assistant through self-improvement, without any human labels identifying harmful outputs...',
    tags: ['Safety', 'RLHF'],
    pdfUrl: SAMPLE_PDF
  }
];

export const EMPTY_MARKDOWN = '';

export const DEFAULT_BIB_FILE = `@article{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N and Kaiser, {\\L}ukasz and Polosukhin, Illia},
  journal={Advances in neural information processing systems},
  volume={30},
  year={2017}
}

@article{hu2021lora,
  title={LoRA: Low-Rank Adaptation of Large Language Models},
  author={Hu, Edward J and Shen, Yelong and Wallis, Phillip and Allen-Zhu, Zeyuan and Li, Yuanzhi and Wang, Shean and Wang, Lu and Chen, Weizhu},
  journal={arXiv preprint arXiv:2106.09685},
  year={2021}
}`;

export const INITIAL_PROJECT_FILES: ProjectFile[] = [
  {
    id: 'main.md',
    name: 'main.md',
    type: 'file',
    content: EMPTY_MARKDOWN,
    extension: 'md'
  },
  {
    id: 'references.bib',
    name: 'references.bib',
    type: 'file',
    content: DEFAULT_BIB_FILE,
    extension: 'bib'
  },
  {
    id: 'figures',
    name: 'figures',
    type: 'folder',
    content: ''
  }
];

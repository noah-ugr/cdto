"""
Author: Noah Masegosa Caceres 
Center: @ugr

PDFWiki: Carga un manual PDF, lo fragmenta, vectoriza y permite consultas RAG para enriquecer la narrativa.
Mejorado con NomenclatureParser para interpretaciones precisas de la nomenclatura del Petri Net.
"""

import os
import re
import shutil
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, CSVLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from input_agent.src.nomenclature_parser import NomenclatureParser

class PDFWiki:
    def __init__(self, pdf_path, persist_dir="./chroma_db_data"):
        """
        persist_dir: Carpeta donde se guardarán los datos vectoriales.
        """
        self.embedding_fn = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_db = None
        
        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            print(f"💾 Cargando Wiki existente desde '{persist_dir}'")
            self.vector_db = Chroma(
                persist_directory=persist_dir,
                embedding_function=self.embedding_fn,
                collection_name="plant_manual"
            )
        else:
            print(f"⚙️ DB no encontrada. Creando nueva desde: {pdf_path}...")
            self._ingest_pdf(pdf_path, persist_dir)
        
    def _ingest_pdf(self, pdf_path, persist_dir):
        if not os.path.exists(pdf_path):
            print(f"⚠️ AVISO: No se encontró {pdf_path}. El Agente funcionará sin definiciones.")
            return

        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=50)
        chunks = splitter.split_documents(docs)
        
        self.vector_db = Chroma.from_documents(
            documents=chunks, 
            embedding=self.embedding_fn,
            collection_name="plant_manual",
            persist_directory=persist_dir 
        )
        print(f"✅ Wiki creada y guardada en disco ({len(chunks)} fragmentos).")

    def consult(self, query):
        if not self.vector_db:
            return "No definition (PDF missing)."
            
        results = self.vector_db.similarity_search(query, k=1)
        if results:
            return results[0].page_content.replace("\n", " ")
        return "Definition not found in manual."

    def consult_petri_node(self, node_id: str, node_type: str = "auto") -> str:
        """
        Consulta precisa para nodos del Petri Net usando NomenclatureParser.
        
        Args:
            node_id: ID del nodo (ej: 'p731', 't0007')
            node_type: "place", "transition", o "auto" (detección automática)
            
        Returns:
            Descripción del nodo enriquecida con contexto de nomenclatura
        """
        if not self.vector_db:
            return "No definition (PDF missing)."
        
        # Usar NomenclatureParser para construir query precisa
        query = NomenclatureParser.build_rag_query(node_id, node_type)
        
        # Log para debugging
        print(f"   🔍 RAG Query para {node_id}: {query}")
        
        results = self.vector_db.similarity_search(query, k=2)  # k=2 para mejor contexto
        
        if results:
            best_result = results[0].page_content.replace("\n", " ")
            
            # Enriquecer con descripción del schema
            schema_desc = NomenclatureParser.get_enhanced_description(node_id, node_type)
            enriched = f"[{schema_desc}] {best_result}"
            
            return enriched
        
        # Fallback: retornar descripción del schema
        schema_desc = NomenclatureParser.get_enhanced_description(node_id, node_type)
        return f"{schema_desc} (Manual definition not found in RAG database)"

    def force_update(self, pdf_path, persist_dir="./chroma_db_data"):
        """Llama a esto si has cambiado el PDF y necesitas reconstruir la DB."""
        if os.path.exists(persist_dir):
            shutil.rmtree(persist_dir)
        self._ingest_pdf(pdf_path, persist_dir)


class EpisodicCSVWiki:
    def __init__(self, csv_path, persist_dir="./chroma_episodic_db"):
        self.csv_path = csv_path
        self.persist_dir = persist_dir  # Guardamos esto para usarlo luego si hace falta
        self.embedding_fn = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_db = None
        
        # 1. Intentar cargar DB existente
        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            print(f"🧠 Cargando Memoria Episódica desde '{persist_dir}'")
            self.vector_db = Chroma(
                persist_directory=persist_dir,
                embedding_function=self.embedding_fn,
                collection_name="episodic_failures"
            )
        else:
            # 2. Si no hay DB, intentamos ingestar CSV
            if os.path.exists(csv_path):
                print(f"⚙️ Indexando historial de errores desde: {csv_path}...")
                self._ingest_csv(csv_path, persist_dir)
            
            # 3. RED DE SEGURIDAD: Si después de todo sigue siendo None (CSV vacío o error),
            # inicializamos una DB vacía para que no falle el programa.
            if self.vector_db is None:
                print("✨ Inicializando Memoria Episódica vacía (Lista para aprender).")
                self.vector_db = Chroma(
                    embedding_function=self.embedding_fn, 
                    collection_name="episodic_failures",
                    persist_directory=persist_dir
                )

    def _ingest_csv(self, csv_path, persist_dir):
        """Lee el CSV y crea vectores."""
        loader = CSVLoader(file_path=csv_path, encoding="utf-8")
        try:
            docs = loader.load()
        except Exception:
            docs = [] # Si falla la lectura, asumimos vacío
        
        if not docs:
            print("⚠️ CSV encontrado pero sin datos. Se iniciará DB vacía.")
            return # Al retornar aquí, el __init__ captura el None y crea la DB vacía

        self.vector_db = Chroma.from_documents(
            documents=docs, 
            embedding=self.embedding_fn,
            collection_name="episodic_failures",
            persist_directory=persist_dir
        )
        print(f"✅ Memoria actualizada: {len(docs)} experiencias traumáticas indexadas.")

    def consult_failures(self, query, score_threshold=0.4):
        if not self.vector_db:
            return None

        # Chroma puede fallar si la colección está vacía al buscar
        try:
            results = self.vector_db.similarity_search_with_score(query, k=1)
        except Exception:
            return None # Colección vacía o error de índice

        if not results:
            return None

        doc, score = results[0]
        
        if score < score_threshold:
            print(f"🛡️ GATEKEEPER ALERT (Score: {score:.2f}): Patrón de error detectado.")
            return doc.page_content
            
        return None

    def add_fresh_memory(self, user_query, error_msg, report):
        """
        Método CRÍTICO: Añade un nuevo error a la DB en tiempo real.
        """
        if self.vector_db is None:
            self.vector_db = Chroma(
                embedding_function=self.embedding_fn, 
                collection_name="episodic_failures",
                persist_directory=self.persist_dir
            )

        content = f"User Query: {user_query}\nValidation Errors: {error_msg}\nEpisodic Report: {report}"
        
        new_doc = Document(page_content=content, metadata={"source": "realtime"})
        
        self.vector_db.add_documents([new_doc])
        print("🧠 Nueva experiencia traumática añadida a la memoria a largo plazo.")

class TXTWiki:
    def __init__(self, doc_path: str):
        # 1. Leer el archivo TXT plano
        with open(doc_path, "r", encoding="utf-8") as f:
            txt_content = f.read()

        # 2. Dividir exactamente por la separación de las fichas
        text_splitter = CharacterTextSplitter(
            separator="\n---\n",
            chunk_size=10,  # Irrelevante aquí, el separador manda
            chunk_overlap=0
        )
        
        raw_chunks = text_splitter.create_documents([txt_content])
        
        # 3. Inyección de Metadatos (La clave para RAG)
        self.chunks = []
        for chunk in raw_chunks:
            content = chunk.page_content.strip()
            if not content:
                continue
                
            metadata = {}
            # Buscar explícitamente el ID en la ficha
            id_match = re.search(r'ID:\s*([a-zA-Z0-9_]+)', content)
            if id_match:
                metadata["node_id"] = id_match.group(1)
                
            # Buscar el TYPE para añadirlo como metadato y hacer más bonita la salida
            type_match = re.search(r'TYPE:\s*(.*)', content)
            if type_match:
                metadata["node_type"] = type_match.group(1).strip()
                
            self.chunks.append(Document(page_content=content, metadata=metadata))
        
        # 4. Crear Base Vectorial (Usamos una colección nueva para evitar chocar con datos viejos)
        self.vector_db = Chroma.from_documents(
            documents=self.chunks,
            embedding=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2"),
            collection_name="petri_txt_collection" 
        )

    def consult_petri_node(self, query_id: str, node_type: str = "place") -> str:
        """
        Busca la ficha exacta usando metadatos y, si no, usa similitud semántica.
        """
        # Limpiamos el ID por si entra con dólares, comillas, etc.
        clean_id = re.sub(r'[\$\s\'\"`]', '', query_id)
        
        # 1. Búsqueda prioritaria usando el filtro de metadatos exacto
        results = self.vector_db.similarity_search(
            query=f"ID: {clean_id}", 
            k=3, 
            filter={"node_id": clean_id} 
        )
        
        # 2. Fallback por si el filtro no engancha
        if not results:
            results = self.vector_db.similarity_search(
                query=f"{clean_id} {node_type}", 
                k=3
            )
        
        # 3. Formatear la salida para el LLM
        if results:
            context_fragments = []
            seen_content = set()
            
            for res in results:
                content = res.page_content.strip()
                if content in seen_content:
                    continue
                seen_content.add(content)
                
                # Extraemos el tipo de los metadatos que inyectamos antes
                card_type = res.metadata.get("node_type", "Unknown Source")
                
                # Conservamos los saltos de línea para que el LLM vea la ficha perfecta
                context_fragments.append(f"SOURCE [{card_type}]:\n{content}")
            
            return "\n\n========================\n\n".join(context_fragments)
            
        return f"No context found for {node_type} ID: {clean_id}"
(ns umlpy.python-source
  "Python LanguageSource: module path -> .py file, `def` / `class` / `Class.method` lookup."
  (:require [clojure.java.io :as io]
            [clojure.string :as str]
            [uml-viewer.source :as source])
  (:import [java.util.regex Pattern]))

(defn src-root []
  (or (System/getenv "UMLPY_SRC") "."))

(defn module->path
  [ns-name]
  (when ns-name
    (let [rel (str/replace (str ns-name) "." "/")
          candidates [(str (src-root) "/" rel ".py")
                      (str (src-root) "/" rel "/__init__.py")]]
      (first (filter #(.isFile (io/file %)) candidates)))))

(defn- indent-of [line]
  (count (take-while #{\space \tab} line)))

(defn- find-line
  "Index of the first line at or after `from` matching `re`, or nil."
  [lines from re]
  (first (keep-indexed (fn [i line] (when (and (>= i from) (re-find re line)) i)) lines)))

(defn- def-re [indented? member]
  (Pattern/compile (str "^" (if indented? "\\s+" "")
                        "(?:async\\s+)?(?:def|class)\\s+" (Pattern/quote member) "\\b")))

(defn member-index
  "0-based line of `member-name` (`f`, `Cls`, or `Cls.method`), or nil."
  [lines member-name]
  (let [[owner member] (str/split (str member-name) #"\." 2)]
    (if member
      (when-let [cls (find-line lines 0 (def-re false owner))]
        (find-line lines (inc cls) (def-re true member)))
      (find-line lines 0 (def-re false owner)))))

(defn- block-end
  "Index after the indented block whose header is at `start`."
  [lines start]
  (let [base (indent-of (nth lines start))
        ;; A closing bracket at header indent belongs to a multi-line signature.
        ends-block? (fn [line] (and (not (str/blank? line))
                                    (<= (indent-of line) base)
                                    (not (re-find #"^\s*[)\]}]" line))))]
    (or (first (keep-indexed (fn [i line] (when (and (> i start) (ends-block? line)) i)) lines))
        (count lines))))

(defn extract-member [source member-name]
  (let [lines (str/split-lines source)]
    (when-let [start (member-index lines member-name)]
      (str/trimr (str/join "\n" (subvec (vec lines) start (block-end lines start)))))))

(defn member-line [source member-name]
  (when-let [i (member-index (str/split-lines source) member-name)]
    (inc i)))

(defrecord PythonSource []
  source/LanguageSource
  (locate [_ ident] (module->path (:ns ident)))
  (extract [_ source ident] (extract-member source (:name ident)))
  (start-line [_ source ident] (member-line source (:name ident)))
  (title [_ ident] (str (:ns ident) ":" (:name ident))))

(def impl (->PythonSource))

(source/register! :python impl)

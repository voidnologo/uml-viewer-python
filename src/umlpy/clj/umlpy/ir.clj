(ns umlpy.ir
  "Upstream IR generator over facts that `umlpy scan` already extracted."
  (:require [clojure.edn :as edn]
            [uml-viewer.graph :as graph]
            [uml-viewer.application.ir-generator :as ir-generator]))

(defrecord FactsGraph [facts]
  graph/LanguageGraph
  (scan [_ _ _] facts))

(defn -main [policy-path facts-path & [out-path]]
  (let [facts (edn/read-string (slurp facts-path))]
    (println "Wrote" (ir-generator/generate (->FactsGraph facts) policy-path out-path))))

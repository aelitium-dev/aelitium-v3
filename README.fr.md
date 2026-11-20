[English](README.md) | [Français](README.fr.md)

# AELITIUM

AELITIUM est une bibliothèque Python et un outil en ligne de commande pour
regrouper des interactions IA enregistrées dans des bundles de preuves techniques,
vérifier leur cohérence hors ligne et comparer les enregistrements. Chaque bundle
réunit les données enregistrées et un manifeste qui décrit les contrôles.

Une équipe peut examiner le bundle d’une autre équipe ou d’un fournisseur sans
accéder à son environnement de production. La vérification porte sur les
enregistrements fournis. Elle ne prouve pas que l’interaction a eu lieu.

Ce README présente la version **0.4.0**, disponible sur [PyPI](https://pypi.org/project/aelitium/0.4.0/).
Les tags et releases GitHub historiques ont été supprimés ; aucune release GitHub
n’est actuellement disponible.

## Fonctionnalités

- Capturer les appels OpenAI, Anthropic et LiteLLM pris en charge via des connecteurs facultatifs.
- Créer un bundle local à partir d’une interaction enregistrée.
- Vérifier les données fournies hors ligne à l’aide des empreintes et du schéma enregistrés.
- Comparer les bundles pris en charge avec une base de comparaison et un résultat explicites.
- Repérer les appels de modèles de langage (LLM) pris en charge par analyse
  statique du code Python.

La [liste des fonctionnalités sur main](https://github.com/aelitium-dev/aelitium-v3/blob/main/FEATURE_MATRIX.md),
sections 1-13, précise les chemins pris en charge et les limites de la version 0.4.0.
Les sections suivantes décrivent des travaux non publiés. La capture et l’analyse
statique ne couvrent pas tous les appels LLM.

## Installation

Python 3.10 ou une version ultérieure est nécessaire. Les dépendances de base sont
`cryptography>=41` et `jsonschema>=4.18`. Les SDK des fournisseurs sont facultatifs.
Dans un nouveau répertoire de travail :

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install "aelitium==0.4.0"
```

Ces commandes utilisent Bash. L’installation peut télécharger des dépendances.
Une fois le paquet installé, l’exemple ci-dessous fonctionne hors ligne.

## Exemple

Cet exemple utilise des données synthétiques. Il n’appelle ni modèle ni API de fournisseur.
Le même enregistrement est utilisé dans les deux versions linguistiques.

```bash
cat > recording.json <<'JSON'
{
  "schema_version": "ai_output_v1",
  "ts_utc": "2026-01-01T00:00:00Z",
  "model": "synthetic-example",
  "prompt": "What is the capital of France?",
  "output": "Paris."
}
JSON

aelitium pack --input recording.json --out bundle
aelitium verify-bundle ./bundle
```

Lorsque la vérification réussit, elle indique `STATUS=VALID rc=0`.
Cet exemple n’est pas signé et ne contient pas de lien enregistré entre requête
et réponse. Les options de vérification par défaut autorisent ces deux absences.

Utilisez un répertoire de sortie neuf et un seul processus d’écriture par destination.
Les fichiers sont écrits successivement. Un échec peut laisser une sortie partielle.
En cas d’échec, ne transmettez pas les fichiers partiels aux outils de lecture.

## Limites

`VALID` signifie que les éléments fournis ont satisfait aux contrôles sélectionnés.
Ce résultat ne prouve ni que l’interaction a eu lieu, ni que le fournisseur a exécuté
la requête, ni que la réponse est vraie, correcte ou sans risque. Il n’établit pas
que la capture est complète, ni ce qui a causé la réponse, l’identité complète de
l’appel réel, la fiabilité de l’horodatage historique, une autorisation ou la
conformité juridique ou réglementaire.

La comparaison n’établit ni causalité, ni dérive du modèle, ni faute du fournisseur.

Un bundle de remplacement cohérent peut aussi réussir la vérification.
Pour contrôler un enregistrement attendu, conservez une empreinte ou une clé de confiance indépendante.
Les signatures sont facultatives. Une clé publique incluse dans un bundle ne constitue
pas une référence de confiance indépendante.

Les bundles conservent le contenu enregistré. Examinez les prompts, les réponses
et les métadonnées avant de les partager. Les empreintes n’anonymisent pas les données.

## Documentation

Les liens ci-dessous suivent la branche `main` actuelle. Consultez la version et
le statut indiqués dans chaque document pour utiliser le paquet PyPI 0.4.0.

- [Documentation du dépôt (main)](https://github.com/aelitium-dev/aelitium-v3/tree/main/docs)
- [Connecteurs de capture (main)](https://github.com/aelitium-dev/aelitium-v3/blob/main/docs/INTEGRATION_CAPTURE.md)
- [Règles de comparaison pour la version 0.4.0 (main)](https://github.com/aelitium-dev/aelitium-v3/blob/main/docs/CANONICAL_REQUEST.md#impact-on-compare)
- [Contribuer au projet](CONTRIBUTING.md)

Ce dépôt contient aussi des travaux non publiés. Consultez le [journal des versions](CHANGELOG.md)
et la [documentation du dépôt](docs/INDEX.md) pour leur historique et les guides propres à chaque version.

## Licence et sécurité

Le paquet 0.4.0 publié est distribué sous [licence Apache-2.0](LICENSE).
Conservez les [mentions d’attribution](NOTICE). Pour signaler une vulnérabilité,
suivez la [politique de sécurité](SECURITY.md).
Toute nouvelle distribution reste soumise à l’examen de la provenance, de la titularité des droits
et des conditions de publication.

WITH base AS (
	SELECT
		pr.id AS requisition_id,
		v.name AS vessel,
		pr.code AS case_id,
		pr.description,
		STRING_AGG(DISTINCT pc.name, ', ') AS categories,
   		STRING_AGG(DISTINCT SPLIT_PART(pc.name, '-', 1), '|') AS category_codes,
		STRING_AGG(DISTINCT RTRIM(suppliers.full_name, ' *'), ', ') AS supplier,
		prs.name AS rqn_status,
		--prs.label AS rqn_status_label,
	    CASE
	        WHEN EXISTS (
	            SELECT 1 FROM review_processes rp
	            WHERE rp.entity_id = pr.id
	              AND rp.entity_type = 'purchasing_requisition'
	              AND rp.deleted_at IS NULL
	              AND NOT EXISTS (
	                  SELECT 1 FROM review_process_steps rps
	                  JOIN review_process_substeps rpss
	                      ON rpss.review_process_step_id = rps.id
	                  WHERE rps.review_process_id = rp.id
	                    AND rps.is_required = true
	                    AND rpss.completed_by_id IS NULL
	              )
	              AND EXISTS (
	                  SELECT 1 FROM purchasing_requisition_item_supplier_details prisd
	                  JOIN purchasing_requisition_suppliers prs2
	                      ON prs2.id = prisd.requisition_supplier_id
	                  WHERE prs2.requisition_id = pr.id
	                    AND (prisd.total_proposed_price IS NOT NULL
	                         OR prisd.approved_quantity IS NOT NULL)
	              )
	        ) THEN true
	        ELSE false
	    END AS is_approved,
		p_created_by.full_name AS created_by,
		--pr.created_at AS created_at,
		pr.updated_at AS updated_at
	FROM purchasing_requisitions                                pr
	LEFT JOIN purchasing_requisition_items                      pri
	    ON pr.id = pri.requisition_id
	LEFT JOIN purchasing_categories                             pc
	    ON pc.id = pri.category_id
	LEFT JOIN purchasing_requisition_statuses                   prs
	    ON prs.id = pr.status_id
	LEFT JOIN purchasing_requisition_suppliers                  prsu
	    ON prsu.requisition_id = pr.id
	LEFT JOIN parties                                           suppliers
	    ON suppliers.id = prsu.supplier_id
	LEFT JOIN vessels                                           v
	    ON v.id = pr.vessel_id
	LEFT JOIN parties											p_created_by
	    ON p_created_by.id = pr.created_by_id
	WHERE
	    pr.deleted_at IS NULL
	    AND pr.rejected = false
	    AND pr.is_template = false
	    AND v.name NOT LIKE '%TEST%'
	    AND (suppliers.full_name IS NULL OR suppliers.full_name NOT LIKE '%TEST%')
		AND pc.name NOT LIKE 'CRW-%'
		--AND pr.code LIKE 'AGSO-CRW%'
		--AND pr.id = 5995
		AND prs.label = 'po'
	GROUP BY
	    pr.id,
	    v.name,
	    pr.code,
	    prs.name,
	    prs.label,
		p_created_by.full_name
	ORDER BY pr.id DESC
)
SELECT * FROM base
WHERE is_approved = true;

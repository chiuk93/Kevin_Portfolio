
-- Large Claim data pull

/*
1. Create table

2. Insert membership and claims data for 2019

3. Update data to 2020

4. Drop Table
*/


drop table member_info if exists;

create temp table member_info (
	yr			varchar(4) not null,
	member_id_nbr 		varchar(80) not null,
	member_gender 		varchar(20),
	member_age 		int,
	member_birth_dt 	date,
	member_zip_cd		varchar(15), 
	total_exp_2019		numeric(13,2),
	total_claim_cnt		int
);

-- Update table with membership data as of 2019
insert into member_info(
	
	select distinct
	substr(rev_month,1,4) as yr,
	t1.member_id,
	t1.member_gender_cd,
	t1.member_age,
	t1.member_birth_dt,
	t1.member_zip_cd,
	t2.paid_amt,
	t2.claim_cnt
	
	
	from (
			select distinct 
			rev_month,
			member_id,
			member_gender_cd,
			member_birth_dt,
			member_age,
			member_zip_cd,
			
			-- Need to rank data to get the latest member_age and member_zip_cd for each member since these could change throughout the year
			row_number() over (partition by member_id,member_gender_cd,member_birth_dt, member_age, member_zip_cd order by rev_month desc) as row_rank
			
			
			from member
			where substr(rev_month,1,4) = '2019'
			and member_state_cd = 'CA'
			and network_cd = 'PPOX'  -- PPO members only
			
			
	) as t1
	left join (
				
				select 
				member_id,
				count(distinct icn_num) as claim_cnt,
				sum(amt_paid) as paid_amt

				
				from claims a
				
					
				where
				to_char(fdos_dt,'yyyymm') >= '201901'
				and to_char(fdos_dt,'yyyymm') <= '201912'
				and member_state_cd = 'CA'
				and network_cd in ('PPOX') 
				and paid_or_denied_cd = 'P' --P for Paid, D for Denied
			
				group by 1
	) as t2
	on t1.member_id = t2.member_id
	
	where t1.row_rank = 1
	and t2.member_id is not null 

	
);


-- update data to 2020
update member_info t1
set t1.yr = t3.yr, t1.member_id_nbr = t3.member_id, t1.member_gender = t3.member_gender_cd, t1.member_age = t3.member_age, t1.member_birth_dt = t3.member_birth_dt, t1.member_zip_cd = t3.member_zip_cd, t1.total_exp_2019 = t3.paid_amt, t1.total_claim_cnt = t3.claim_cnt
from (
		select distinct
		substr(rev_month,1,4) as yr,
		t1.member_id,
		t1.member_gender_cd,
		t1.member_age,
		t1.member_birth_dt,
		t1.member_zip_cd,
		t2.paid_amt,
		t2.claim_cnt
		
		
		from (
				select distinct 
				rev_month,
				member_id,
				member_gender_cd,
				member_birth_dt,
				member_age,
				member_zip_cd,
				
				-- Need to rank data to get the latest member_age and member_zip_cd for each member since these could change throughout the year
				row_number() over (partition by member_id,member_gender_cd,member_birth_dt order by rev_month desc) as row_rank
				
				
				from member
				where substr(rev_month,1,4) = '2020'
				and member_state_cd = 'CA'
				and network_cd = 'PPOX'  -- PPO members only
		
				
		) as t1
		left join (
					
					select 
					member_id,
					count(distinct icn_num) as claim_cnt,
					sum(amt_paid) as paid_amt
	
					
					from claims a
					
						
					where
					to_char(fdos_dt,'yyyymm') >= '202001'
					and to_char(fdos_dt,'yyyymm') <= '202012'
					and member_state_cd = 'CA'
					and network_cd in ('PPOX') 
				
					group by 1
		) as t2
		on t1.member_id = t2.member_id
		
		where t1.row_rank = 1
		and t2.member_id is not null 
	) t3
where t1.yr = '2019'
;

-- Create CTE temporary tables for analyses

with member_info2 as (
	select
	yr,
	member_id_nbr,
	member_gender,
	member_age,
	sum(total_exp_2019) as total_exp,
	sum(case when total_exp_2019 >= 250000 then total_exp_2019 else 0 end) as total_exp_250K,
	sum(case when total_exp_2019 >= 150000 then total_exp_2019 else 0 end) as total_exp_150K,
	sum(case when total_exp_2019 >= 100000 then total_exp_2019 else 0 end) as total_exp_100K,
	sum(case when total_exp_2019 >= 50000 then total_exp_2019 else 0 end) as total_exp_50K,
	sum(case when total_exp_2019 < 50000 then total_exp_2019 else 0 end) as total_exp_less50K
	
	from member_info 
	
	group by 1,2,3,4
)

-- How many members between age 0-18 have incurred more than $50K in claims?
select 
count(distinct member_id_nbr) as member_count
from member_info2
where total_exp > 50000;

-- What is the age distribution for members who have incurred more than $50K in claims? and what is the aggregate expense?
select 
case when member_age <= 18 then '0-18'
	 when member_age between 19 and 30 then '19-30'
	 when member_age between 31 and 40 then '31-40'
	 when member_age between 41 and 50 then '41-50'
 	 when member_age between 51 and 65 then '51-65'
	 else '65+' 
	 end as age_group,
sum(total_exp_50K) as total_exp_50K

from member_info2
group by 1;

-- Drop table 
drop table member_info;

